from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from utils.logging import get_logger
from .concepts import extract_concepts_from_material
from .config import DEFAULT_CALL_BUDGET
from .db import LearnDB
from .diagnosis import (
    get_diagnostic_report,
    get_diagnostic_session,
    start_diagnostic_session,
    submit_diagnostic_answer,
)
from .ingest import ingest_document
from .llm import get_llm_client
from .mastery import update_mastery
from .misconception import run_misconception_pipeline
from .questions import generate_questions_for_concept
from .revision import get_revision_quiz, schedule_concept_revision
from .schemas import (
    Concept,
    ErrorType,
    Mastery,
    Material,
    MaterialKind,
    Question,
    RevisionItem,
)

LOGGER = get_logger("blinky.learn.api")

_DB: Optional[LearnDB] = None


def get_db() -> LearnDB:
    global _DB
    if _DB is None:
        _DB = LearnDB()
    return _DB


def handle_learn_rpc(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Central request dispatcher for all Preppy Learn RPC actions (§4).
    Protocol: {"type": "learn.<action>", ...} -> returns JSON result dict.
    """
    db = get_db()
    llm_client = get_llm_client()
    student_id = params.get("student_id", "local")

    try:
        # ---------------------------------------------------------------------
        # 1. System Status & AI Transparency
        # ---------------------------------------------------------------------
        if action == "learn.status":
            status = llm_client.get_provider_status()
            materials = db.list_materials(student_id=student_id)
            all_masteries = db.list_all_masteries(student_id=student_id)
            due_queue = db.list_revision_queue(student_id=student_id)
            open_misconceptions = db.list_open_misconceptions(student_id=student_id)

            return {
                "success": True,
                "status": status,
                "stats": {
                    "materials_count": len(materials),
                    "concepts_count": len(all_masteries),
                    "due_revision_count": len(due_queue),
                    "open_misconceptions_count": len(open_misconceptions),
                },
            }

        # ---------------------------------------------------------------------
        # 2. Materials Ingestion
        # ---------------------------------------------------------------------
        elif action in ("learn.materials.upload", "learn.material.create"):
            title = params.get("title", "Untitled Document")
            content = params.get("content", "")
            kind_str = params.get("kind", "notes").lower()
            file_type = params.get("file_type", "txt")
            kind = MaterialKind(kind_str) if kind_str in MaterialKind.__members__ else MaterialKind.notes

            material = ingest_document(
                title=title,
                content=content,
                kind=kind,
                file_type=file_type,
                student_id=student_id,
                db=db,
            )
            return {
                "success": True,
                "material": material.model_dump(),
                "is_syllabus": material.kind == MaterialKind.syllabus,
            }

        elif action in ("learn.materials.list", "learn.material.list"):
            materials = db.list_materials(student_id=student_id)
            return {
                "success": True,
                "materials": [m.model_dump() for m in materials],
            }

        # ---------------------------------------------------------------------
        # 3. Concept Map
        # ---------------------------------------------------------------------
        elif action in ("learn.concepts.extract", "learn.material.extract_concepts"):
            mat_id = params.get("material_id", "")
            material = db.get_material(mat_id)
            if not material:
                return {"success": False, "error": f"Material {mat_id} not found"}

            concepts = extract_concepts_from_material(material, llm_client=llm_client, db=db)
            return {
                "success": True,
                "material_id": mat_id,
                "concepts": [c.model_dump() for c in concepts],
            }

        elif action == "learn.concepts.list":
            mat_id = params.get("material_id")
            concepts = db.list_concepts(material_id=mat_id)
            enriched = []
            for c in concepts:
                m = db.get_mastery(c.id, student_id=student_id)
                enriched.append({
                    "concept": c.model_dump(),
                    "mastery": m.model_dump() if m else None,
                })
            return {"success": True, "concepts": enriched}

        # ---------------------------------------------------------------------
        # 4. Diagnostic Assessment
        # ---------------------------------------------------------------------
        elif action == "learn.diagnostic.start":
            mat_id = params.get("material_id", "")
            count = int(params.get("question_count", 10))
            session = start_diagnostic_session(mat_id, db=db, question_count=count, student_id=student_id)

            # Fetch first question
            first_q = db.get_question(session.question_ids[0]) if session.question_ids else None

            return {
                "success": True,
                "session_id": session.session_id,
                "total_questions": len(session.question_ids),
                "current_index": 0,
                "first_question": first_q.model_dump() if first_q else None,
            }

        elif action == "learn.diagnostic.get_question":
            session_id = params.get("session_id", "")
            session = get_diagnostic_session(session_id)
            if not session:
                return {"success": False, "error": f"Session {session_id} not found"}

            idx = int(params.get("index", session.current_index))
            if idx >= len(session.question_ids):
                return {"success": True, "completed": True}

            qid = session.question_ids[idx]
            q = db.get_question(qid)
            return {
                "success": True,
                "index": idx,
                "total": len(session.question_ids),
                "question": q.model_dump() if q else None,
            }

        elif action == "learn.diagnostic.submit":
            session_id = params.get("session_id", "")
            answer_text = params.get("answer_text", "")
            selected_option = params.get("selected_option")
            reasoning_text = params.get("reasoning_text", "")
            confidence = params.get("confidence")
            time_ms = int(params.get("time_ms", 0))

            res = submit_diagnostic_answer(
                session_id=session_id,
                answer_text=answer_text,
                selected_option=selected_option,
                reasoning_text=reasoning_text,
                confidence=confidence,
                time_ms=time_ms,
                db=db,
            )
            return {"success": True, "result": res}

        elif action == "learn.diagnostic.report":
            session_id = params.get("session_id", "")
            report = get_diagnostic_report(session_id, db=db)
            return {"success": True, "report": report}

        # ---------------------------------------------------------------------
        # 5. Misconception Engine & Remediation
        # ---------------------------------------------------------------------
        elif action == "learn.misconception.analyze":
            attempt_id = params.get("attempt_id")
            qid = params.get("question_id")
            cid = params.get("concept_id")
            loop_count = int(params.get("loop_count", 1))

            question = db.get_question(qid)
            concept = db.get_concept(cid)
            if not question or not concept:
                return {"success": False, "error": "Question or concept not found"}

            material = db.get_material(concept.material_id)
            if not material:
                material = Material(
                    id=concept.material_id,
                    title="Course Notes",
                    kind=MaterialKind.notes,
                    content_hash="mock",
                    okf_text="Course material content.",
                )

            # Retrieve or construct attempt
            attempts = db.list_attempts_for_concept(cid, student_id=student_id)
            attempt = next((a for a in attempts if a.id == attempt_id), None)
            if not attempt:
                attempt = Attempt(
                    id=attempt_id or "att_temp",
                    student_id=student_id,
                    question_id=qid,
                    concept_id=cid,
                    answer_text=params.get("answer_text", ""),
                    selected_option=params.get("selected_option"),
                    reasoning_text=params.get("reasoning_text", ""),
                    confidence=params.get("confidence", 2),
                    time_ms=int(params.get("time_ms", 5000)),
                    is_correct=False,
                )

            res = run_misconception_pipeline(
                attempt=attempt,
                question=question,
                concept=concept,
                material=material,
                db=db,
                llm_client=llm_client,
                loop_count=loop_count,
            )
            return {"success": True, "analysis": res}

        # ---------------------------------------------------------------------
        # 6. Adaptive Revision Queue & Quiz
        # ---------------------------------------------------------------------
        elif action == "learn.revision.queue":
            max_items = int(params.get("max_items", 20))
            queue = db.list_revision_queue(student_id=student_id, max_items=max_items)
            items = []
            for r in queue:
                c = db.get_concept(r.concept_id)
                m = db.get_mastery(r.concept_id, student_id=student_id)
                items.append({
                    "item": r.model_dump(),
                    "concept": c.model_dump() if c else None,
                    "mastery": m.model_dump() if m else None,
                })
            return {"success": True, "queue": items}

        elif action == "learn.revision.start_quiz":
            max_c = int(params.get("max_concepts", 5))
            quiz = get_revision_quiz(db=db, student_id=student_id, max_concepts=max_c)
            return {"success": True, "quiz": quiz}

        # ---------------------------------------------------------------------
        # 7. Mastery History
        # ---------------------------------------------------------------------
        elif action == "learn.mastery.history":
            cid = params.get("concept_id")
            if not cid:
                return {"success": False, "error": "concept_id is required"}
            history = db.get_mastery_history(cid, student_id=student_id)
            return {"success": True, "history": history}

        # ---------------------------------------------------------------------
        # 8. Read -> Recall (Voice) Mode (§5.2)
        # ---------------------------------------------------------------------
        elif action == "learn.recall.chunks_list":
            mat_id = params.get("material_id")
            c_id = params.get("concept_id")
            chunks = db.list_chunks(material_id=mat_id, concept_id=c_id)
            if not chunks:
                materials = db.list_materials(student_id=student_id)
                from .recall import chunk_document_into_paragraphs, extract_chunk_key_ideas
                for m in materials:
                    if m.kind == MaterialKind.notes:
                        new_chunks = chunk_document_into_paragraphs(m.okf_text, material_id=m.id)
                        concepts = db.list_concepts(m.id)
                        for ch in new_chunks:
                            for c in concepts:
                                if c.name.lower() in ch.text.lower():
                                    ch.concept_id = c.id
                                    break
                            ch.key_ideas = extract_chunk_key_ideas(ch)
                            ch.key_ideas_status = "ready"
                        db.save_chunks(new_chunks)
                        chunks.extend(new_chunks)
            return {"success": True, "chunks": [c.model_dump() for c in chunks]}

        elif action == "learn.recall.chunk_get":
            chunk_id = params.get("chunk_id")
            chunk = None
            if chunk_id:
                chunk = db.get_chunk(chunk_id)
            else:
                due_queue = db.list_revision_queue(student_id=student_id, max_items=5)
                target_concept_id = due_queue[0].concept_id if due_queue else None
                if target_concept_id:
                    c_chunks = db.list_chunks(concept_id=target_concept_id)
                    if c_chunks:
                        chunk = c_chunks[0]
                if not chunk:
                    all_chunks = db.list_chunks()
                    if all_chunks:
                        chunk = all_chunks[0]

            if not chunk:
                return {"success": False, "error": "No chunk available. Please load demo or upload study notes."}

            if not chunk.key_ideas:
                from .recall import extract_chunk_key_ideas
                chunk.key_ideas = extract_chunk_key_ideas(chunk, llm_client)
                chunk.key_ideas_status = "ready"
                db.save_chunk(chunk)

            concept = db.get_concept(chunk.concept_id) if chunk.concept_id else None
            return {
                "success": True,
                "chunk": chunk.model_dump(),
                "concept": concept.model_dump() if concept else None,
            }

        elif action == "learn.recall.analyze":
            chunk_id = params.get("chunk_id")
            if not chunk_id:
                return {"success": False, "error": "chunk_id is required"}
            chunk = db.get_chunk(chunk_id)
            if not chunk:
                return {"success": False, "error": f"Chunk '{chunk_id}' not found"}

            transcript_raw = params.get("transcript_raw", "")
            transcript_final = params.get("transcript_final", transcript_raw)
            peeked = bool(params.get("peeked", False))
            read_ms = int(params.get("read_ms", 0))
            input_method = params.get("input_method", "wispr_flow_dictation")

            from .recall import analyze_recall_transcript
            session, analysis = analyze_recall_transcript(
                chunk=chunk,
                transcript_raw=transcript_raw,
                transcript_final=transcript_final,
                peeked=peeked,
                read_ms=read_ms,
                input_method=input_method,
                db=db,
                llm_client=llm_client,
                student_id=student_id,
            )
            return {
                "success": True,
                "session": session.model_dump(),
                "analysis": analysis.model_dump(),
            }

        elif action == "learn.recall.sessions_list":
            chunk_id = params.get("chunk_id")
            sessions = db.list_recall_sessions(student_id=student_id, chunk_id=chunk_id)
            return {"success": True, "sessions": [s.model_dump() for s in sessions]}

        # ---------------------------------------------------------------------
        # 9. Demo Sample Data Loader (§9)
        # ---------------------------------------------------------------------
        elif action == "learn.sample.load":
            from .sample_loader import load_engineering_physics_sample
            result = load_engineering_physics_sample(db=db, student_id=student_id)
            return {"success": True, "sample": result}

        elif action == "learn.misconception.list_open":
            records = db.list_open_misconceptions(student_id=student_id)
            return {"success": True, "records": records}

        elif action == "learn.mastery.batch":
            c_ids = params.get("concept_ids", [])
            masteries = []
            for cid in c_ids:
                m = db.get_mastery(cid, student_id=student_id)
                if m:
                    masteries.append(m.model_dump())
            return {"success": True, "masteries": masteries}

        else:
            return {"success": False, "error": f"Unknown Preppy RPC action: {action}"}

    except Exception as exc:
        LOGGER.error("Preppy RPC action '%s' failed: %s", action, exc, exc_info=True)
        return {"success": False, "error": str(exc)}

