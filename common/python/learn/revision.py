from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from utils.logging import get_logger
from .config import (
    SM2_INITIAL_EASE,
    SM2_MAX_EASE,
    SM2_MIN_EASE,
)
from .db import LearnDB
from .schemas import (
    Attempt,
    Concept,
    Mastery,
    MasteryBand,
    Question,
    RevisionItem,
)

LOGGER = get_logger("blinky.learn.revision")

# One deterministic human-readable explanation template per reason_code (§5.4)
REASON_TEMPLATES: Dict[str, str] = {
    "OPEN_MISCONCEPTION": "Revisit {concept_name} today because you have an unresolved conceptual misunderstanding.",
    "INCONSISTENT_RECENT": "Revisit {concept_name} today because your recent attempts showed inconsistent understanding ({consistency_pct}% consistency).",
    "WEAK_MASTERY": "Revisit {concept_name} today because your understanding ({mastery_pct}%) is in the weak band and needs reinforcement.",
    "LAPSE_AFTER_SUCCESS": "Revisit {concept_name} today to rebuild momentum following a recent mistake.",
    "SPACED_INTERVAL_DUE": "Scheduled spaced repetition for {concept_name} to strengthen long-term memory consolidation.",
    "NEW_CONCEPT_INITIAL": "Initial revision for {concept_name} following your diagnostic assessment.",
}


def build_explanation_string(
    reason_code: str,
    concept_name: str,
    mastery: float,
    consistency: float,
) -> str:
    """Generates an explainable reason string purely from code templates (§5.4). No AI calls."""
    template = REASON_TEMPLATES.get(reason_code, REASON_TEMPLATES["SPACED_INTERVAL_DUE"])
    return template.format(
        concept_name=concept_name,
        mastery_pct=int(round(mastery * 100)),
        consistency_pct=int(round(consistency * 100)),
    )


def schedule_concept_revision(
    concept: Concept,
    current_item: Optional[RevisionItem],
    mastery: Mastery,
    outcome: float,
    has_open_misconception: bool = False,
    now: Optional[int] = None,
) -> RevisionItem:
    """
    Computes deterministic spaced revision schedule based on modified SM-2 (§5.4).
    Rules:
    - outcome >= 0.8: interval = 1 on 1st success, 3 on 2nd, else round(interval * ease); ease += 0.05
    - 0.4 <= outcome < 0.8: interval = max(1, round(interval * 0.6)); ease -= 0.05
    - outcome < 0.4: interval = 1; ease -= 0.20; if open misconception, due_at = today
    - Inconsistency cap: if consistency < 0.5, interval = min(interval, 2)
    - Mastery band adjustment: weak -> interval capped at 3; strong -> allow interval * 1.2
    """
    current_time = now if now is not None else int(time.time())
    one_day_seconds = 86400

    # Initialize current state
    ease = current_item.ease if current_item else SM2_INITIAL_EASE
    prev_interval = current_item.interval_days if current_item else 1
    consecutive_correct = mastery.consecutive_correct

    reason_code = "SPACED_INTERVAL_DUE"

    if outcome >= 0.80:
        if consecutive_correct <= 1:
            interval = 1
        elif consecutive_correct == 2:
            interval = 3
        else:
            interval = max(1, int(round(prev_interval * ease)))
        ease = min(SM2_MAX_EASE, ease + 0.05)
        reason_code = "SPACED_INTERVAL_DUE"

    elif 0.40 <= outcome < 0.80:
        interval = max(1, int(round(prev_interval * 0.60)))
        ease = max(SM2_MIN_EASE, ease - 0.05)
        reason_code = "LAPSE_AFTER_SUCCESS"

    else:  # outcome < 0.40
        interval = 1
        ease = max(SM2_MIN_EASE, ease - 0.20)
        if has_open_misconception:
            reason_code = "OPEN_MISCONCEPTION"
        else:
            reason_code = "WEAK_MASTERY" if mastery.mastery < 0.40 else "LAPSE_AFTER_SUCCESS"

    # Inconsistency cap: if consistency < 0.5, interval = min(interval, 2)
    if mastery.consistency < 0.50:
        interval = min(interval, 2)
        if reason_code != "OPEN_MISCONCEPTION":
            reason_code = "INCONSISTENT_RECENT"

    # Mastery band adjustment
    if mastery.band == MasteryBand.weak:
        interval = min(interval, 3)
        if reason_code not in ("OPEN_MISCONCEPTION", "INCONSISTENT_RECENT"):
            reason_code = "WEAK_MASTERY"
    elif mastery.band == MasteryBand.strong:
        interval = max(1, int(round(interval * 1.20)))

    # Compute due date
    if has_open_misconception and outcome < 0.40:
        due_at = current_time  # Due immediately today
    else:
        due_at = current_time + (interval * one_day_seconds)

    reason_text = build_explanation_string(
        reason_code=reason_code,
        concept_name=concept.name,
        mastery=mastery.mastery,
        consistency=mastery.consistency,
    )

    return RevisionItem(
        student_id=mastery.student_id,
        concept_id=concept.id,
        due_at=due_at,
        interval_days=interval,
        ease=round(ease, 3),
        last_reviewed_at=current_time,
        reason_code=reason_code,
        reason_text=reason_text,
    )


def get_revision_quiz(
    db: LearnDB,
    student_id: str = "local",
    max_concepts: int = 5,
) -> Dict[str, Any]:
    """
    Selects up to 5 due concepts and serves questions already in the bank (§5.4).
    Prefers questions targeted at resolved or open misconceptions.
    Does NOT require an AI provider to be online.
    """
    queue = db.list_revision_queue(student_id=student_id, max_items=max_concepts)
    if not queue:
        return {"items": [], "total_questions": 0, "message": "No revision items currently due!"}

    quiz_items = []
    total_q = 0

    for rev in queue:
        concept = db.get_concept(rev.concept_id)
        if not concept:
            continue

        questions = db.list_questions_for_concept(rev.concept_id)
        if not questions:
            continue

        # Prefer questions targeting misconceptions or highest difficulty
        selected_q = questions[0]
        quiz_items.append({
            "concept_id": concept.id,
            "concept_name": concept.name,
            "reason_code": rev.reason_code,
            "reason_text": rev.reason_text,
            "interval_days": rev.interval_days,
            "question": selected_q.model_dump(),
        })
        total_q += 1

    return {
        "items": quiz_items,
        "total_questions": total_q,
        "due_count": len(queue),
    }

