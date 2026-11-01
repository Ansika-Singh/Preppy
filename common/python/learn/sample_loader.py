from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from utils.logging import get_logger
from .concepts import extract_concepts_offline
from .db import LearnDB
from .ingest import ingest_document
from .schemas import (
    Concept,
    Material,
    MaterialKind,
    MisconceptionCandidate,
    Question,
    QuestionType,
    SourceSpan,
)

LOGGER = get_logger("blinky.learn.sample_loader")


def load_engineering_physics_sample(db: LearnDB, student_id: str = "local") -> Dict[str, Any]:
    """
    Loads the sample Engineering Physics syllabus, verified notes, and pre-authored question bank (§9).
    Seeds materials, extracts grounded concepts, and attaches sample diagnostic questions.
    """
    sample_dir = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "learn" / "sample"
    if not sample_dir.exists():
        # Fallback to local path relative to workspace root
        sample_dir = Path("docs") / "learn" / "sample"

    syllabus_path = sample_dir / "engineering_physics_syllabus.txt"
    notes_path = sample_dir / "engineering_physics_notes.txt"
    questions_path = sample_dir / "offline_question_bank.json"

    # 1. Ingest Syllabus (Honesty mode: grounded=false)
    syllabus_text = syllabus_path.read_text(encoding="utf-8") if syllabus_path.exists() else "# Physics Syllabus\n1. Mechanics"
    syllabus_mat = ingest_document(
        title="Engineering Physics — Syllabus",
        content=syllabus_text,
        kind=MaterialKind.syllabus,
        file_type="txt",
        student_id=student_id,
        db=db,
    )
    existing_s_concepts = db.list_concepts(syllabus_mat.id)
    if existing_s_concepts:
        syllabus_concepts = existing_s_concepts
    else:
        syllabus_concepts = extract_concepts_offline(syllabus_mat)
        db.save_concepts(syllabus_concepts)

    # 2. Ingest Verified Notes (Grounded mode: grounded=true)
    notes_text = notes_path.read_text(encoding="utf-8") if notes_path.exists() else "# Physics Notes\nF = m*a"
    notes_mat = ingest_document(
        title="Engineering Physics — Lecture Notes",
        content=notes_text,
        kind=MaterialKind.notes,
        file_type="txt",
        student_id=student_id,
        db=db,
    )
    existing_n_concepts = db.list_concepts(notes_mat.id)
    if existing_n_concepts:
        notes_concepts = existing_n_concepts
    else:
        notes_concepts = extract_concepts_offline(notes_mat)
        db.save_concepts(notes_concepts)

    # Map concepts by name
    concept_map = {c.name.lower(): c for c in notes_concepts}

    # 3. Load pre-authored questions
    loaded_questions_count = 0
    if questions_path.exists():
        try:
            q_data = json.loads(questions_path.read_text(encoding="utf-8"))
            for q_raw in q_data.get("questions", []):
                c_name = q_raw.get("concept_name", "").lower()
                matched_concept = None
                for name, c in concept_map.items():
                    if c_name in name or name in c_name:
                        matched_concept = c
                        break

                if not matched_concept and notes_concepts:
                    matched_concept = notes_concepts[0]

                if matched_concept:
                    quote = q_raw.get("source_quote", "")
                    span = SourceSpan(
                        material_id=notes_mat.id,
                        source_name=notes_mat.title,
                        quote=quote,
                    ) if quote else None

                    q = Question(
                        id=f"q_sample_{matched_concept.id[:6]}_{loaded_questions_count}",
                        concept_id=matched_concept.id,
                        type=QuestionType(q_raw.get("type", "mcq")),
                        difficulty=q_raw.get("difficulty", 2),
                        stem=q_raw.get("stem", ""),
                        options=q_raw.get("options", []),
                        correct_answer=q_raw.get("correct_answer", ""),
                        distractor_map=q_raw.get("distractor_map", {}),
                        source_span=span,
                        grounded=span is not None,
                        origin="authored_sample",
                    )
                    db.save_questions([q])

                    # Register candidate misconceptions
                    candidates = [
                        MisconceptionCandidate(
                            id=f"mcand_samp_{loaded_questions_count}_{idx}",
                            concept_id=matched_concept.id,
                            label=misc_label,
                            description=f"Typical misconception for wrong choice: '{opt}'",
                            typical_wrong_answer=opt,
                            origin="authored",
                        )
                        for idx, (opt, misc_label) in enumerate(q.distractor_map.items())
                    ]
                    if candidates:
                        db.save_misconception_candidates(candidates)

                    loaded_questions_count += 1
        except Exception as e:
            LOGGER.error("Failed loading offline question bank: %s", e)

    # 4. Chunk verified notes for Read -> Recall (§5.2)
    import re
    from .recall import chunk_document_into_paragraphs, extract_chunk_key_ideas
    existing_chunks = db.list_chunks(material_id=notes_mat.id)
    if not existing_chunks:
        # Strip metadata header before chunking for optimal reading flow
        clean_notes = re.sub(r"^###\s+SOURCE:[^\n]*\nType:[^\n]*\n+", "", notes_mat.okf_text)
        clean_notes = re.sub(r"^#[^\n]*\n+", "", clean_notes).strip()
        chunks = chunk_document_into_paragraphs(clean_notes, material_id=notes_mat.id)
        for chunk in chunks:
            for c in notes_concepts:
                if c.name.lower() in chunk.text.lower() or any(sp.quote in chunk.text for sp in c.source_spans):
                    chunk.concept_id = c.id
                    break
            if not chunk.concept_id and notes_concepts:
                chunk.concept_id = notes_concepts[0].id
            chunk.key_ideas = extract_chunk_key_ideas(chunk)
            chunk.key_ideas_status = "ready"
        db.save_chunks(chunks)
        chunks_count = len(chunks)
    else:
        chunks_count = len(existing_chunks)

    return {
        "syllabus_material_id": syllabus_mat.id,
        "notes_material_id": notes_mat.id,
        "syllabus_concepts_count": len(syllabus_concepts),
        "notes_concepts_count": len(notes_concepts),
        "questions_count": loaded_questions_count,
        "chunks_count": chunks_count,
    }

