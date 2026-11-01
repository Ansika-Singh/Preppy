from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from utils.logging import get_logger
from .config import (
    MAX_NO_REASONING_CONFIDENCE,
    MAX_REMEDIATION_LOOPS,
    MIN_MISCONCEPTION_CONFIDENCE,
)
from .db import LearnDB
from .ingest import normalize_text_for_search
from .llm import LLMClient, LearnAIError, get_llm_client
from .mastery import update_mastery
from .schemas import (
    Attempt,
    Concept,
    ErrorType,
    Mastery,
    Material,
    MisconceptionAnalysis,
    MisconceptionCandidate,
    MisconceptionRecord,
    MisconceptionState,
    Question,
    QuestionType,
    Remediation,
    SourceSpan,
)

LOGGER = get_logger("blinky.learn.misconception")


# -----------------------------------------------------------------------------
# Step 1: Evidence Gathering
# -----------------------------------------------------------------------------
def gather_evidence(
    attempt: Attempt,
    question: Question,
    concept: Concept,
    material: Material,
    db: LearnDB,
) -> Dict[str, Any]:
    """Collects all diagnostic evidence for error analysis (§5.2 Step 1)."""
    prior_attempts = db.list_attempts_for_concept(concept.id, student_id=attempt.student_id)
    candidates = db.list_misconception_candidates(concept.id)

    # Find distractor hint
    distractor_hint = question.distractor_map.get(attempt.answer_text) or question.distractor_map.get(
        attempt.selected_option or ""
    )

    grounding_quote = concept.source_spans[0].quote if concept.source_spans else material.okf_text[:600]

    return {
        "attempt": attempt,
        "question": question,
        "concept": concept,
        "material": material,
        "prior_attempts": prior_attempts,
        "candidates": candidates,
        "distractor_hint": distractor_hint,
        "grounding_quote": grounding_quote,
    }


# -----------------------------------------------------------------------------
# Step 2: Cheap Classification Heuristics
# -----------------------------------------------------------------------------
def cheap_classification_heuristics(
    attempt: Attempt,
    question: Question,
    evidence: Dict[str, Any],
    prior_mastery: float = 0.50,
) -> Optional[Tuple[ErrorType, float, str]]:
    """
    Evaluates fast deterministic heuristics before model invocation (§5.2 Step 2):
    - Calculation error on numeric questions where reasoning indicates right approach.
    - Careless mistake on high mastery + high confidence + fast response.
    - Distractor prior mapping.
    """
    reasoning = (attempt.reasoning_text or "").lower()

    # 1. Numeric / units question with calculation slip
    if question.type == QuestionType.numeric or any(
        sym in reasoning for sym in ["=", "+", "-", "*", "/", "formula", "calculate"]
    ):
        if len(reasoning) > 10 and not attempt.is_correct:
            # Right method keywords
            if any(term in reasoning for term in ["f=ma", "proportional", "multiply", "divide", "substitute"]):
                return (ErrorType.calculation_error, 0.75, "Arithmetic/algebraic slip with valid method")

    # 2. Careless mistake: high mastery, high confidence, fast response (< 3.5s)
    if prior_mastery >= 0.70 and attempt.confidence == 3 and attempt.time_ms < 3500:
        return (ErrorType.careless_mistake, 0.80, "High prior mastery and rapid high-confidence response")

    return None


# -----------------------------------------------------------------------------
# Step 3 & 4: Structured Analysis & Strict Deterministic Validation
# -----------------------------------------------------------------------------
def analyze_misconception(
    attempt: Attempt,
    question: Question,
    concept: Concept,
    material: Material,
    db: LearnDB,
    llm_client: Optional[LLMClient] = None,
) -> Tuple[MisconceptionAnalysis, MisconceptionState]:
    """
    Executes Steps 3 and 4:
    [AI] Structured classification via schema.
    [D] Strict validation:
        - evidence_quote MUST be an exact substring of student text.
        - confidence < 0.55 downgrades to uncertain.
        - conceptual_misunderstanding requires two independent signals to be 'confirmed', else 'suspected'.
    """
    client = llm_client or get_llm_client()
    evidence = gather_evidence(attempt, question, concept, material, db)

    current_m = db.get_mastery(concept.id, student_id=attempt.student_id)
    prior_mastery = current_m.mastery if current_m else 0.50

    heuristic = cheap_classification_heuristics(attempt, question, evidence, prior_mastery)

    candidate_str = "\n".join(
        f"- ID: {c.id} | Label: {c.label} | Common answer: {c.typical_wrong_answer}"
        for c in evidence["candidates"]
    ) or "[No previously identified candidate misconceptions]"

    student_text = f"{attempt.answer_text} {attempt.reasoning_text}".strip()

    try:
        analysis: MisconceptionAnalysis = client.generate_structured(
            prompt_name="misconception_analysis",
            template_args={
                "concept_name": concept.name,
                "concept_description": concept.description,
                "grounding_context": evidence["grounding_quote"],
                "candidate_misconceptions": candidate_str,
                "question_stem": question.stem,
                "correct_answer": question.correct_answer,
                "student_answer": attempt.answer_text,
                "distractor_hint": evidence["distractor_hint"] or "None",
                "reasoning_text": attempt.reasoning_text or "[None provided]",
                "confidence": str(attempt.confidence or 2),
                "time_ms": str(attempt.time_ms),
            },
            schema=MisconceptionAnalysis,
            max_retries=2,
            max_tokens=1000,
        )
    except (LearnAIError, Exception) as exc:
        LOGGER.warning("LLM misconception analysis unavailable (%s). Falling back to deterministic prior.", exc)
        # Fallback using heuristic or distractor mapping
        if evidence["distractor_hint"]:
            analysis = MisconceptionAnalysis(
                error_type=ErrorType.conceptual_misunderstanding,
                new_misconception_label=evidence["distractor_hint"],
                confidence=0.70,
                evidence_quote=None,
                rationale="Matched distractor misconception map (offline heuristic)",
                needs_probe=False,
            )
        elif heuristic:
            err_type, conf, rat = heuristic
            analysis = MisconceptionAnalysis(
                error_type=err_type,
                confidence=conf,
                evidence_quote=None,
                rationale=rat,
                needs_probe=False,
            )
        else:
            analysis = MisconceptionAnalysis(
                error_type=ErrorType.uncertain,
                confidence=0.40,
                evidence_quote=None,
                rationale="Insufficient evidence to categorize error without model",
                needs_probe=True,
            )

    # -------------------------------------------------------------------------
    # Deterministic Validation Pipeline (§5.2 Step 4)
    # -------------------------------------------------------------------------
    # 1. No reasoning text provided: cap confidence at MAX_NO_REASONING_CONFIDENCE (0.60)
    if not (attempt.reasoning_text or "").strip():
        if analysis.confidence > MAX_NO_REASONING_CONFIDENCE:
            LOGGER.info("Cap confidence at 0.60: no written reasoning provided")
            analysis.confidence = MAX_NO_REASONING_CONFIDENCE

    # 2. Strict evidence quote substring verification
    if analysis.evidence_quote:
        quote = analysis.evidence_quote.strip()
        norm_quote = normalize_text_for_search(quote)
        norm_student = normalize_text_for_search(student_text)
        if norm_quote not in norm_student:
            LOGGER.warning("Discarded non-verbatim evidence quote: '%s'", quote)
            analysis.evidence_quote = None
            # If the model fabricated an evidence quote, downgrade confidence
            analysis.confidence = min(analysis.confidence, 0.50)

    # 3. Confidence threshold check: < 0.55 downgrades to uncertain
    if analysis.confidence < MIN_MISCONCEPTION_CONFIDENCE:
        LOGGER.info("Confidence %.2f below 0.55 threshold: marking as uncertain", analysis.confidence)
        analysis.error_type = ErrorType.uncertain
        analysis.needs_probe = True
        return analysis, MisconceptionState.uncertain

    # 4. State determination for conceptual_misunderstanding:
    # Requires TWO independent signals to be 'confirmed':
    # Signal A: selected distractor has mapped misconception.
    # Signal B: student reasoning quote confirmed or prior failed attempt with same issue.
    state = MisconceptionState.suspected
    if analysis.error_type == ErrorType.conceptual_misunderstanding:
        has_distractor_signal = bool(evidence["distractor_hint"])
        has_reasoning_signal = bool(analysis.evidence_quote)
        prior_failed = any(not a.is_correct for a in evidence["prior_attempts"][:-1])

        if (has_distractor_signal and has_reasoning_signal) or (has_distractor_signal and prior_failed):
            state = MisconceptionState.confirmed
            LOGGER.info("Misconception marked CONFIRMED: two independent signals verified")
        else:
            state = MisconceptionState.suspected
            LOGGER.info("Misconception marked SUSPECTED: single signal observed")
    elif analysis.error_type == ErrorType.uncertain:
        state = MisconceptionState.uncertain

    return analysis, state


# -----------------------------------------------------------------------------
# Step 5: Targeted Remediation
# -----------------------------------------------------------------------------
def generate_remediation(
    analysis: MisconceptionAnalysis,
    concept: Concept,
    material: Material,
    question: Question,
    attempt: Attempt,
    llm_client: Optional[LLMClient] = None,
) -> Remediation:
    """
    Generates targeted remediation (§5.2 Step 5):
    - Why the student's belief is wrong.
    - Plain-language core idea (<= 3 sentences).
    - Vivid real-world analogy.
    - New follow-up question testing the SAME misconception with a DIFFERENT surface form.
    - Clear separation of verified notes grounding vs AI explanation.
    """
    client = llm_client or get_llm_client()
    misc_label = analysis.new_misconception_label or analysis.misconception_id or "Intuitive Conceptual Flaw"

    grounding_span = concept.source_spans[0] if concept.source_spans else None
    grounding_text = grounding_span.quote if grounding_span else material.okf_text[:600]

    try:
        remediation: Remediation = client.generate_structured(
            prompt_name="remediation",
            template_args={
                "concept_name": concept.name,
                "misconception_label": misc_label,
                "grounding_context": grounding_text,
                "original_question": question.stem,
                "student_mistake": f"Answered '{attempt.answer_text}'. Reasoning: '{attempt.reasoning_text}'",
            },
            schema=Remediation,
            max_retries=2,
            max_tokens=1500,
        )
        # Ensure follow-up question has required ids
        remediation.followup_question.id = f"q_remed_{uuid.uuid4().hex[:8]}"
        remediation.followup_question.concept_id = concept.id
        remediation.grounded_in_span = grounding_span
        return remediation

    except (LearnAIError, Exception) as exc:
        LOGGER.warning("AI remediation failed (%s). Using deterministic remediation template.", exc)
        # Offline deterministic remediation
        fol_q = Question(
            id=f"q_remed_{uuid.uuid4().hex[:8]}",
            concept_id=concept.id,
            type=QuestionType.mcq,
            difficulty=question.difficulty,
            stem=f"Consider a different scenario for {concept.name}: If the net force acting on a system is tripled while mass remains unchanged, what must happen to acceleration?",
            options=[
                "Acceleration triples proportionally",
                "Acceleration stays unchanged because mass is constant",
                "Acceleration is cut to one-third",
                "Acceleration cannot be determined without velocity",
            ],
            correct_answer="Acceleration triples proportionally",
            distractor_map={
                "Acceleration stays unchanged because mass is constant": misc_label,
                "Acceleration is cut to one-third": "Inverts direct force-acceleration proportionality",
                "Acceleration cannot be determined without velocity": "Confuses velocity with acceleration",
            },
            source_span=grounding_span,
            grounded=grounding_span is not None,
            origin="authored_remediation",
        )
        return Remediation(
            why_wrong=f"Believing '{misc_label}' ignores the direct cause-and-effect relationship established by {concept.name}.",
            core_idea=f"In {concept.name}, acceleration is directly proportional to the applied net force and inversely proportional to mass. When force changes, acceleration must change immediately.",
            analogy="Think of pushing a shopping trolley: if you suddenly push it twice as hard, it accelerates twice as fast, even though the trolley's mass hasn't changed.",
            followup_question=fol_q,
            grounded_in_span=grounding_span,
        )


# -----------------------------------------------------------------------------
# Step 6 & 7: Verification Loop & Persistence
# -----------------------------------------------------------------------------
def run_misconception_pipeline(
    attempt: Attempt,
    question: Question,
    concept: Concept,
    material: Material,
    db: LearnDB,
    llm_client: Optional[LLMClient] = None,
    loop_count: int = 1,
) -> Dict[str, Any]:
    """
    Executes the full end-to-end misconception engine (§5.2).
    Returns structured analysis, remediation, follow-up item, and updated record.
    """
    # 1 & 2 & 3 & 4: Analyze and validate
    analysis, state = analyze_misconception(attempt, question, concept, material, db, llm_client)

    # 5: Generate targeted remediation
    remediation = generate_remediation(analysis, concept, material, question, attempt, llm_client)

    # Save follow-up question to DB
    db.save_questions([remediation.followup_question])

    # 6: Verification loop escalation check (§5.2 Step 6)
    escalation_style = "standard_analogy"
    exceeded_cap = False

    if loop_count == 2:
        escalation_style = "worked_example"
    elif loop_count >= MAX_REMEDIATION_LOOPS:
        escalation_style = "simpler_sub_question"
        exceeded_cap = True
        LOGGER.info("Loop cap of %s reached for concept %s: scheduling revision", MAX_REMEDIATION_LOOPS, concept.id)

    # 7: Persist misconception record (§5.2 Step 7)
    record_id = f"mrec_{uuid.uuid4().hex[:8]}"
    record = MisconceptionRecord(
        id=record_id,
        attempt_id=attempt.id,
        concept_id=concept.id,
        error_type=analysis.error_type,
        misconception_id=analysis.misconception_id,
        state=state,
        confidence=analysis.confidence,
        evidence_quote=analysis.evidence_quote,
        explanation={
            "rationale": analysis.rationale,
            "why_wrong": remediation.why_wrong,
            "core_idea": remediation.core_idea,
            "analogy": remediation.analogy,
            "escalation_style": escalation_style,
            "loop_count": loop_count,
        },
        created_at=int(time.time()),
    )
    db.save_misconception_record(record)

    # Apply penalty update to mastery with error classification
    current_m = db.get_mastery(concept.id, student_id=attempt.student_id)
    if current_m:
        updated_m = update_mastery(
            current_mastery=current_m,
            attempt=attempt,
            question=question,
            classified_error=analysis.error_type,
        )
        db.save_mastery(updated_m, attempt_id=attempt.id)

    return {
        "record_id": record_id,
        "error_type": analysis.error_type.value,
        "state": state.value,
        "confidence": analysis.confidence,
        "evidence_quote": analysis.evidence_quote,
        "rationale": analysis.rationale,
        "needs_probe": analysis.needs_probe,
        "why_wrong": remediation.why_wrong,
        "core_idea": remediation.core_idea,
        "analogy": remediation.analogy,
        "escalation_style": escalation_style,
        "exceeded_loop_cap": exceeded_cap,
        "followup_question": remediation.followup_question.model_dump(),
        "grounded_source": remediation.grounded_in_span.quote if remediation.grounded_in_span else None,
        "source_label": "From your notes (verified)" if remediation.grounded_in_span else "Explanation (AI-generated)",
    }

