from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from utils.logging import get_logger
from .config import (
    CHUNK_MAX_WORDS,
    CHUNK_MIN_WORDS,
    MIN_RECALL_RATIO,
    MIN_RECALL_WORDS,
    PEEKED_COVERAGE_CAP,
    RECITED_COVERAGE_CAP,
    RECITATION_TRIGRAM_THRESHOLD,
)
from .db import LearnDB
from .llm import LLMClient, LearnAIError, get_llm_client
from .mastery import update_mastery
from .misconception import run_misconception_pipeline
from .revision import schedule_concept_revision
from .schemas import (
    Attempt,
    Chunk,
    ChunkKeyIdea,
    Concept,
    ErrorType,
    ExtraClaim,
    ExtraClaimType,
    Material,
    Question,
    QuestionType,
    RecallAnalysisResult,
    RecallKeyIdeaEvaluation,
    RecallSession,
    RecallStatus,
    SourceSpan,
)

LOGGER = get_logger("blinky.learn.recall")

PROMPTS_DIR = Path(__file__).parent / "prompts"


# -----------------------------------------------------------------------------
# Exact Substring Quote Verifier (§5.2)
# -----------------------------------------------------------------------------
def verify_exact_substring(quote: Optional[str], full_text: str) -> Optional[str]:
    """
    Guarantees quote is an exact, verbatim substring of full_text.
    Discards or corrects hallucinated quotes. Never passes unverified text.
    """
    if not quote or not full_text:
        return None
    clean_q = quote.strip()
    if not clean_q:
        return None
    if clean_q in full_text:
        return clean_q

    # Attempt case-insensitive match and return the exact slice from full_text
    idx = full_text.lower().find(clean_q.lower())
    if idx != -1:
        return full_text[idx : idx + len(clean_q)]

    # Discard non-matching quote
    return None


# -----------------------------------------------------------------------------
# Step 1: Chunking Engine (~80 - 220 words)
# -----------------------------------------------------------------------------
def chunk_document_into_paragraphs(
    text: str,
    material_id: str,
    concept_id: Optional[str] = None,
    target_min_words: int = CHUNK_MIN_WORDS,
    target_max_words: int = CHUNK_MAX_WORDS,
) -> List[Chunk]:
    """
    Chunks educational document text into cohesive paragraph units (~80-220 words).
    Preserves document order with sequential indices.
    """
    raw_paras = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if not raw_paras:
        if text.strip():
            raw_paras = [text.strip()]
        else:
            return []

    merged_paras: List[str] = []
    current_buf: List[str] = []
    current_word_count = 0

    for para in raw_paras:
        w_count = len(para.split())
        if w_count > target_max_words:
            # Paragraph itself is too large: split sentences into smaller segments
            sentences = re.split(r"(?<=[.!?])\s+", para)
            sent_buf: List[str] = []
            sent_words = 0
            for sent in sentences:
                sw = len(sent.split())
                if sent_words + sw > target_max_words and sent_buf:
                    merged_paras.append(" ".join(sent_buf))
                    sent_buf = [sent]
                    sent_words = sw
                else:
                    sent_buf.append(sent)
                    sent_words += sw
            if sent_buf:
                if current_buf:
                    merged_paras.append("\n\n".join(current_buf))
                    current_buf = []
                    current_word_count = 0
                merged_paras.append(" ".join(sent_buf))
            continue

        if current_word_count + w_count < target_min_words:
            current_buf.append(para)
            current_word_count += w_count
        else:
            if current_buf:
                current_buf.append(para)
                merged_paras.append("\n\n".join(current_buf))
                current_buf = []
                current_word_count = 0
            else:
                merged_paras.append(para)

    if current_buf:
        merged_paras.append("\n\n".join(current_buf))

    chunks: List[Chunk] = []
    for idx, p_text in enumerate(merged_paras):
        c_id = f"chunk_{material_id}_{idx}"
        w_cnt = len(p_text.split())
        chunks.append(
            Chunk(
                id=c_id,
                material_id=material_id,
                concept_id=concept_id,
                idx=idx,
                text=p_text,
                word_count=w_cnt,
                key_ideas=[],
                key_ideas_status="pending",
            )
        )

    return chunks


# -----------------------------------------------------------------------------
# Step 2: Recitation Detection via Word Trigrams (§5.2)
# -----------------------------------------------------------------------------
def calculate_recitation_ratio(transcript: str, paragraph: str) -> float:
    """
    Computes word-trigram overlap between transcript and paragraph.
    If ratio > 0.60, indicates student is mostly reciting/memorizing verbatim
    rather than explaining in their own words.
    """
    def extract_words(s: str) -> List[str]:
        return re.findall(r"\b[a-zA-Z0-9'-]+\b", s.lower())

    t_words = extract_words(transcript)
    p_words = extract_words(paragraph)

    if len(t_words) < 3:
        return 0.0

    t_trigrams = [tuple(t_words[i : i + 3]) for i in range(len(t_words) - 2)]
    p_trigrams = set(tuple(p_words[i : i + 3]) for i in range(len(p_words) - 2))

    if not t_trigrams or not p_trigrams:
        return 0.0

    matches = sum(1 for tg in t_trigrams if tg in p_trigrams)
    return round(matches / len(t_trigrams), 3)


# -----------------------------------------------------------------------------
# LLM Response Schemas
# -----------------------------------------------------------------------------
class KeyIdeaRaw(BaseModel):
    id: Optional[str] = None
    claim: str
    supporting_quote: str


class ChunkKeyIdeasOutput(BaseModel):
    key_ideas: List[KeyIdeaRaw] = Field(default_factory=list)


class RecallEvalRaw(BaseModel):
    key_idea_id: str
    status: str
    student_quote: Optional[str] = None
    feedback: Optional[str] = ""


class ExtraClaimRaw(BaseModel):
    claim: str
    student_quote: str
    type: str


class RecallAnalysisOutput(BaseModel):
    evaluations: List[RecallEvalRaw] = Field(default_factory=list)
    extra_claims: List[ExtraClaimRaw] = Field(default_factory=list)
    summary: str


def _extract_fallback_key_ideas(chunk: Chunk) -> List[ChunkKeyIdea]:
    """Deterministic fallback key idea extractor when LLM is offline."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", chunk.text) if len(s.strip()) > 15]
    if not sentences:
        sentences = [chunk.text[:120]]

    selected = sentences[:4]
    key_ideas: List[ChunkKeyIdea] = []
    for i, sent in enumerate(selected, 1):
        clean_sent = sent.strip()
        key_ideas.append(
            ChunkKeyIdea(
                id=f"{chunk.id}_ki_{i}",
                claim=clean_sent[:100],
                supporting_quote=clean_sent,
            )
        )
    return key_ideas


def extract_chunk_key_ideas(
    chunk: Chunk,
    llm_client: Optional[LLMClient] = None,
) -> List[ChunkKeyIdea]:
    """
    Extracts 3 to 6 atomic claims for a chunk, verifying each quote
    is an exact substring of the chunk text.
    """
    client = llm_client or get_llm_client()
    try:
        res: ChunkKeyIdeasOutput = client.generate_structured(
            prompt_name="chunk_key_ideas",
            template_args={"paragraph_text": chunk.text},
            schema=ChunkKeyIdeasOutput,
        )
        verified_ideas: List[ChunkKeyIdea] = []
        for idx, item in enumerate(res.key_ideas, 1):
            claim = item.claim.strip()
            valid_quote = verify_exact_substring(item.supporting_quote, chunk.text)
            if valid_quote and claim:
                verified_ideas.append(
                    ChunkKeyIdea(
                        id=f"{chunk.id}_ki_{idx}",
                        claim=claim,
                        supporting_quote=valid_quote,
                    )
                )

        if len(verified_ideas) >= 2:
            return verified_ideas
    except Exception as e:
        LOGGER.warning("Error generating chunk key ideas via LLM: %s. Using fallback.", e)

    return _extract_fallback_key_ideas(chunk)


# -----------------------------------------------------------------------------
# Step 4: Recall Analysis Pipeline
# -----------------------------------------------------------------------------
def analyze_recall_transcript(
    chunk: Chunk,
    transcript_raw: str,
    transcript_final: str,
    peeked: bool = False,
    read_ms: int = 0,
    input_method: str = "wispr_flow_dictation",
    db: Optional[LearnDB] = None,
    llm_client: Optional[LLMClient] = None,
    student_id: str = "local",
) -> Tuple[RecallSession, RecallAnalysisResult]:
    """
    Executes the complete Read -> Recall analysis pipeline (§5.2):
    1. Pre-checks: brevity & recitation.
    2. Structured LLM key idea evaluation & claim extraction.
    3. Verbatim quote substring enforcement.
    4. Coverage score calculation (discounted if peeked/recited).
    5. Contradiction routing into Misconception Engine.
    6. Mastery & Spaced Revision updates.
    7. Persistence.
    """
    transcript = transcript_final.strip()
    words = transcript.split()
    word_count = len(words)
    chunk_words = max(1, chunk.word_count)

    # 1. Fast client/code pre-checks (§5.2 Step 5)
    # Too short (< 15 words or < 30% of expected length)
    is_too_short = (word_count < MIN_RECALL_WORDS) or (word_count / chunk_words < MIN_RECALL_RATIO)
    if is_too_short:
        evals = [
            RecallKeyIdeaEvaluation(
                key_idea_id=ki.id,
                claim=ki.claim,
                status=RecallStatus.missed,
                student_quote=None,
                notes_quote=ki.supporting_quote,
                feedback="Not enough detail provided to evaluate this concept.",
            )
            for ki in chunk.key_ideas
        ]
        analysis_res = RecallAnalysisResult(
            chunk_id=chunk.id,
            coverage_score=0.0,
            raw_coverage_score=0.0,
            is_too_short=True,
            recitation_ratio=0.0,
            is_recited=False,
            peeked=peeked,
            evaluations=evals,
            extra_claims=[],
            misconceptions_detected=[],
            summary="Too brief to evaluate — explain the main points in a sentence or two.",
            linked_misconception_record_ids=[],
        )
        session = RecallSession(
            id=f"recall_{uuid.uuid4().hex[:8]}",
            student_id=student_id,
            chunk_id=chunk.id,
            concept_id=chunk.concept_id,
            read_ms=read_ms,
            peeked=peeked,
            input_method=input_method,
            transcript_raw=transcript_raw,
            transcript_final=transcript_final,
            coverage=0.0,
            recitation_ratio=0.0,
            accuracy_flags={"is_too_short": True, "is_recited": False, "peeked": peeked},
            analysis=analysis_res,
            created_at=int(time.time()),
        )
        if db:
            db.save_recall_session(session)
        return session, analysis_res

    # Recitation check
    recitation_ratio = calculate_recitation_ratio(transcript, chunk.text)
    is_recited = recitation_ratio > RECITATION_TRIGRAM_THRESHOLD

    # Ensure key ideas are present
    if not chunk.key_ideas:
        chunk.key_ideas = extract_chunk_key_ideas(chunk, llm_client)
        if db:
            db.save_chunk(chunk)

    # 2. LLM Evaluation against key ideas
    client = llm_client or get_llm_client()
    raw_evals: List[Dict[str, Any]] = []
    raw_extras: List[Dict[str, Any]] = []
    summary_text = ""

    try:
        key_ideas_json = json.dumps([ki.model_dump() for ki in chunk.key_ideas], indent=2)
        analysis_out: RecallAnalysisOutput = client.generate_structured(
            prompt_name="recall_analysis",
            template_args={
                "paragraph_text": chunk.text,
                "key_ideas_json": key_ideas_json,
                "transcript_final": transcript,
            },
            schema=RecallAnalysisOutput,
        )
        raw_evals = [e.model_dump() for e in analysis_out.evaluations]
        raw_extras = [ec.model_dump() for ec in analysis_out.extra_claims]
        summary_text = analysis_out.summary
    except Exception as e:
        LOGGER.info("LLM unavailable for recall analysis (%s); using deterministic heuristic.", e)

    # Fallback heuristic evaluation if LLM was unavailable or failed
    if not raw_evals:
        for ki in chunk.key_ideas:
            # Check overlap between key idea words and transcript words
            ki_words = set(re.findall(r"\b\w{4,}\b", ki.claim.lower()))
            t_words = set(re.findall(r"\b\w{4,}\b", transcript.lower()))
            overlap = len(ki_words.intersection(t_words)) / max(1, len(ki_words))

            if overlap >= 0.5:
                status_str = "covered"
            elif overlap >= 0.2:
                status_str = "partially_covered"
            else:
                status_str = "missed"

            raw_evals.append({
                "key_idea_id": ki.id,
                "status": status_str,
                "student_quote": None,
                "feedback": f"Evaluated based on content coverage ({int(overlap * 100)}% keyword alignment).",
            })
        summary_text = "Good recall attempt! Review the missed points to deepen your memory."

    # Build validated evaluations enforcing exact substring quotes (§5.2)
    eval_map = {e.get("key_idea_id"): e for e in raw_evals}
    validated_evals: List[RecallKeyIdeaEvaluation] = []
    covered_count = 0.0
    contradicted_ideas: List[ChunkKeyIdea] = []

    for ki in chunk.key_ideas:
        e = eval_map.get(ki.id)
        if e:
            status_val = e.get("status", "missed").lower()
            if status_val == "covered":
                st = RecallStatus.covered
                covered_count += 1.0
            elif status_val == "partially_covered":
                st = RecallStatus.partially_covered
                covered_count += 0.5
            elif status_val == "contradicted":
                st = RecallStatus.contradicted
                contradicted_ideas.append(ki)
            else:
                st = RecallStatus.missed

            raw_sq = e.get("student_quote")
            valid_sq = verify_exact_substring(raw_sq, transcript)
            fb = e.get("feedback") or ""
        else:
            st = RecallStatus.missed
            valid_sq = None
            fb = "Not mentioned in recall."

        validated_evals.append(
            RecallKeyIdeaEvaluation(
                key_idea_id=ki.id,
                claim=ki.claim,
                status=st,
                student_quote=valid_sq,
                notes_quote=ki.supporting_quote,
                feedback=fb,
            )
        )

    # Process extra claims
    validated_extras: List[ExtraClaim] = []
    misconceptions_detected: List[str] = []
    for ec in raw_extras:
        c_type = ec.get("type", "neutral").lower()
        if c_type == "correct_extension":
            ect = ExtraClaimType.correct_extension
        elif c_type == "misconception":
            ect = ExtraClaimType.misconception
            misconceptions_detected.append(ec.get("claim", ""))
        elif c_type == "irrelevant":
            ect = ExtraClaimType.irrelevant
        else:
            ect = ExtraClaimType.neutral

        sq = verify_exact_substring(ec.get("student_quote"), transcript) or transcript[:60]
        validated_extras.append(
            ExtraClaim(
                claim=ec.get("claim", ""),
                student_quote=sq,
                type=ect,
            )
        )

    # 3. Credit & Scoring Calculation (§5.2)
    total_ideas = max(1, len(chunk.key_ideas))
    raw_coverage = round(covered_count / total_ideas, 3)
    final_coverage = raw_coverage

    if peeked:
        final_coverage = min(final_coverage, PEEKED_COVERAGE_CAP)
    if is_recited:
        final_coverage = min(final_coverage, RECITED_COVERAGE_CAP)

    final_coverage = max(0.0, min(1.0, round(final_coverage, 2)))

    # 4. Contradiction & Misconception Bridge to Engine 2 (§5.2 & §11)
    linked_record_ids: List[str] = []
    concept: Optional[Concept] = None
    material: Optional[Material] = None

    if db:
        if chunk.concept_id:
            concept = db.get_concept(chunk.concept_id)
        if not concept and chunk.material_id:
            concepts = db.list_concepts(chunk.material_id)
            if concepts:
                concept = concepts[0]
        if chunk.material_id:
            material = db.get_material(chunk.material_id)

    if (contradicted_ideas or misconceptions_detected) and db and concept and material:
        for c_idea in contradicted_ideas:
            # Find student quote or fall back to transcript
            matching_eval = next((ev for ev in validated_evals if ev.key_idea_id == c_idea.id), None)
            student_evidence = matching_eval.student_quote if matching_eval else transcript

            attempt = Attempt(
                id=f"att_recall_{uuid.uuid4().hex[:8]}",
                student_id=student_id,
                concept_id=concept.id,
                chunk_id=chunk.id,
                source="recall",
                answer_text=student_evidence or transcript,
                reasoning_text=f"Student recall contradicted key claim: '{c_idea.claim}'",
                confidence=3,
                is_correct=False,
                score=0.0,
                time_ms=read_ms,
                session_id="recall_flow",
                created_at=int(time.time()),
            )
            db.save_attempt(attempt)

            # Synthesize targeted question for the pipeline
            question = Question(
                id=f"q_recall_{uuid.uuid4().hex[:8]}",
                concept_id=concept.id,
                type=QuestionType.explain,
                difficulty=2,
                stem=f"Explain the relationship regarding: {c_idea.claim}",
                options=[],
                correct_answer=c_idea.claim,
                distractor_map={},
                source_span=SourceSpan(
                    material_id=material.id,
                    source_name=material.title,
                    quote=c_idea.supporting_quote,
                ),
                grounded=True,
                origin="recall_contradiction",
            )
            db.save_questions([question])

            try:
                pipeline_res = run_misconception_pipeline(
                    attempt=attempt,
                    question=question,
                    concept=concept,
                    material=material,
                    db=db,
                    llm_client=llm_client,
                )
                linked_record_ids.append(pipeline_res["record_id"])
                LOGGER.info("Successfully routed recall contradiction to Misconception Tutor: %s", pipeline_res["record_id"])
            except Exception as ex:
                LOGGER.warning("Could not execute misconception pipeline for contradiction: %s", ex)

    # 5. Mastery and Adaptive Revision Feed (§5.2 & §5.3 & §5.4)
    if db and concept:
        # Create an attempt representing the recall session outcome
        attempt_id = f"att_rec_{uuid.uuid4().hex[:8]}"
        is_success = final_coverage >= 0.70 and not contradicted_ideas
        recall_attempt = Attempt(
            id=attempt_id,
            student_id=student_id,
            question_id=f"recall_{chunk.id}",
            concept_id=concept.id,
            chunk_id=chunk.id,
            source="recall",
            answer_text=transcript[:300],
            reasoning_text=f"Read -> Recall session. Coverage: {int(final_coverage * 100)}%",
            confidence=2,
            is_correct=is_success,
            score=final_coverage,
            time_ms=read_ms,
            session_id="recall_session",
            created_at=int(time.time()),
        )
        db.save_attempt(recall_attempt)

        # Update mastery
        curr_mastery = db.get_mastery(concept.id, student_id=student_id)
        if curr_mastery:
            dummy_q = Question(
                id="q_recall_eval",
                concept_id=concept.id,
                type=QuestionType.explain,
                difficulty=2,
                stem=f"Recall explanation of {concept.name}",
                correct_answer="High recall coverage",
            )
            upd_mastery = update_mastery(
                current_mastery=curr_mastery,
                attempt=recall_attempt,
                question=dummy_q,
            )
            db.save_mastery(upd_mastery, attempt_id=attempt_id)

            # Schedule spaced revision
            rev_item = db.get_revision_item(concept.id, student_id=student_id)
            has_open_misc = len(linked_record_ids) > 0
            new_rev = schedule_concept_revision(
                concept=concept,
                current_item=rev_item,
                mastery=upd_mastery,
                outcome=final_coverage,
                has_open_misconception=has_open_misc,
            )
            db.save_revision_item(new_rev)

    # 6. Build Final Result & Session
    analysis_res = RecallAnalysisResult(
        chunk_id=chunk.id,
        coverage_score=final_coverage,
        raw_coverage_score=raw_coverage,
        is_too_short=False,
        recitation_ratio=recitation_ratio,
        is_recited=is_recited,
        peeked=peeked,
        evaluations=validated_evals,
        extra_claims=validated_extras,
        misconceptions_detected=misconceptions_detected,
        summary=summary_text or f"You covered {int(final_coverage * 100)}% of the key ideas.",
        linked_misconception_record_ids=linked_record_ids,
    )

    session = RecallSession(
        id=f"recall_{uuid.uuid4().hex[:8]}",
        student_id=student_id,
        chunk_id=chunk.id,
        concept_id=chunk.concept_id,
        read_ms=read_ms,
        peeked=peeked,
        input_method=input_method,
        transcript_raw=transcript_raw,
        transcript_final=transcript_final,
        coverage=final_coverage,
        recitation_ratio=recitation_ratio,
        accuracy_flags={"is_too_short": False, "is_recited": is_recited, "peeked": peeked},
        analysis=analysis_res,
        created_at=int(time.time()),
    )

    if db:
        db.save_recall_session(session)

    return session, analysis_res
