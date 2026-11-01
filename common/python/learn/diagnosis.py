from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from utils.logging import get_logger
from .config import DEFAULT_DIAGNOSTIC_QUESTION_COUNT, MAX_DIAGNOSTIC_QUESTION_COUNT
from .db import LearnDB
from .mastery import update_mastery
from .questions import generate_questions_for_concept
from .schemas import (
    Attempt,
    Concept,
    Mastery,
    MasteryBand,
    Material,
    Question,
    QuestionType,
)

LOGGER = get_logger("blinky.learn.diagnosis")


class DiagnosticSession(BaseModel):
    session_id: str
    material_id: str
    student_id: str = "local"
    question_ids: List[str]
    current_index: int = 0
    attempts: List[Attempt] = Field(default_factory=list)
    completed: bool = False
    created_at: int = 0


# In-memory session registry (resilient to reloads)
_ACTIVE_SESSIONS: Dict[str, DiagnosticSession] = {}


def start_diagnostic_session(
    material_id: str,
    db: LearnDB,
    question_count: int = DEFAULT_DIAGNOSTIC_QUESTION_COUNT,
    student_id: str = "local",
) -> DiagnosticSession:
    """
    Initializes an 8-12 question diagnostic assessment across concepts (§5.1).
    Picks ~1 question per concept for highest priority concepts.
    """
    material = db.get_material(material_id)
    if not material:
        raise ValueError(f"Material {material_id} not found")

    concepts = db.list_concepts(material_id)
    if not concepts:
        raise ValueError(f"No concepts found for material {material_id}. Extract concepts first.")

    target_count = max(1, min(MAX_DIAGNOSTIC_QUESTION_COUNT, question_count))
    selected_questions: List[Question] = []

    # Prioritize concepts that have few or no attempts
    concept_priorities = []
    for c in concepts:
        m = db.get_mastery(c.id, student_id=student_id)
        attempts = m.attempts if m else 0
        concept_priorities.append((attempts, c))

    concept_priorities.sort(key=lambda x: x[0])

    for _, c in concept_priorities:
        if len(selected_questions) >= target_count:
            break
        # Check existing questions in DB
        qs = db.list_questions_for_concept(c.id)
        if not qs:
            qs = generate_questions_for_concept(c, material, count=1, db=db)
        if qs:
            selected_questions.append(qs[0])

    session_id = f"diag_{uuid.uuid4().hex[:8]}"
    session = DiagnosticSession(
        session_id=session_id,
        material_id=material_id,
        student_id=student_id,
        question_ids=[q.id for q in selected_questions],
        current_index=0,
        attempts=[],
        completed=False,
        created_at=int(time.time()),
    )

    _ACTIVE_SESSIONS[session_id] = session
    LOGGER.info("Started diagnostic session %s with %s questions", session_id, len(selected_questions))
    return session


def get_diagnostic_session(session_id: str) -> Optional[DiagnosticSession]:
    return _ACTIVE_SESSIONS.get(session_id)


def submit_diagnostic_answer(
    session_id: str,
    answer_text: str,
    selected_option: Optional[str],
    reasoning_text: str,
    confidence: Optional[int],
    time_ms: int,
    db: LearnDB,
) -> Dict[str, Any]:
    """
    Evaluates student answer, updates mastery if correct, records attempt in DB,
    and signals if misconception remediation is required (§5.1, §5.2).
    """
    session = _ACTIVE_SESSIONS.get(session_id)
    if not session:
        raise ValueError(f"Diagnostic session {session_id} not found")

    if session.completed or session.current_index >= len(session.question_ids):
        return {"completed": True, "message": "Diagnostic session already completed."}

    qid = session.question_ids[session.current_index]
    question = db.get_question(qid)
    if not question:
        raise ValueError(f"Question {qid} not found")

    # Evaluate correctness
    is_correct = False
    clean_student_ans = (selected_option or answer_text).strip()
    if question.type == QuestionType.mcq:
        is_correct = clean_student_ans.lower() == question.correct_answer.strip().lower()
    else:
        # Short / explain: keyword or exact match fallback
        is_correct = question.correct_answer.strip().lower() in clean_student_ans.lower()

    attempt_id = f"att_{uuid.uuid4().hex[:8]}"
    score = 1.0 if is_correct else 0.0

    attempt = Attempt(
        id=attempt_id,
        student_id=session.student_id,
        question_id=qid,
        concept_id=question.concept_id,
        answer_text=clean_student_ans,
        selected_option=selected_option,
        reasoning_text=reasoning_text.strip(),
        confidence=confidence,
        is_correct=is_correct,
        score=score,
        time_ms=time_ms,
        session_id=session_id,
        created_at=int(time.time()),
    )

    db.save_attempt(attempt)
    session.attempts.append(attempt)
    session.current_index += 1

    # Update concept mastery
    current_m = db.get_mastery(question.concept_id, student_id=session.student_id)
    if current_m is None:
        current_m = Mastery(
            student_id=session.student_id,
            concept_id=question.concept_id,
            mastery=0.50,
            attempts=0,
            band=MasteryBand.insufficient_evidence,
        )

    updated_m = update_mastery(
        current_mastery=current_m,
        attempt=attempt,
        question=question,
        is_transfer_question=False,
    )
    db.save_mastery(updated_m, attempt_id=attempt_id)

    # Check if session is now complete
    if session.current_index >= len(session.question_ids):
        session.completed = True

    # Detect if distractor was mapped to a misconception
    distractor_misc = question.distractor_map.get(clean_student_ans)

    return {
        "attempt_id": attempt_id,
        "is_correct": is_correct,
        "score": score,
        "question_id": qid,
        "concept_id": question.concept_id,
        "needs_misconception_analysis": not is_correct,
        "distractor_misconception": distractor_misc,
        "new_mastery": updated_m.mastery,
        "band": updated_m.band.value,
        "has_more": not session.completed,
        "next_index": session.current_index,
        "total_questions": len(session.question_ids),
    }


def get_diagnostic_report(session_id: str, db: LearnDB) -> Dict[str, Any]:
    """Generates overall diagnostic summary once session is complete."""
    session = _ACTIVE_SESSIONS.get(session_id)
    if not session:
        raise ValueError(f"Diagnostic session {session_id} not found")

    concept_results = []
    seen_concepts = set()

    for att in session.attempts:
        if att.concept_id in seen_concepts:
            continue
        seen_concepts.add(att.concept_id)
        concept = db.get_concept(att.concept_id)
        mastery = db.get_mastery(att.concept_id, student_id=session.student_id)
        if concept and mastery:
            concept_results.append({
                "concept_id": concept.id,
                "name": concept.name,
                "mastery": mastery.mastery,
                "band": mastery.band.value,
                "attempts": mastery.attempts,
                "correct": mastery.correct,
                "consistency": mastery.consistency,
            })

    total_attempts = len(session.attempts)
    correct_count = sum(1 for a in session.attempts if a.is_correct)

    return {
        "session_id": session_id,
        "completed": session.completed,
        "total_questions": len(session.question_ids),
        "total_answered": total_attempts,
        "correct_answers": correct_count,
        "accuracy": round(correct_count / total_attempts, 2) if total_attempts > 0 else 0.0,
        "concept_results": concept_results,
    }
