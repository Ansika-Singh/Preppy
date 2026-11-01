from __future__ import annotations

import math
from typing import List, Optional

from utils.logging import get_logger
from .config import (
    ALPHA_BASE,
    BAND_STRONG_MIN,
    BAND_WEAK_MAX,
    CARELESS_MISTAKE_WEIGHT,
    DIFFICULTY_WEIGHTS,
    GUESS_DISCOUNT_CAP,
    STRONG_MIN_ATTEMPTS,
    STRONG_MIN_CONSISTENCY,
)
from .schemas import Attempt, ErrorType, Mastery, MasteryBand, Question, QuestionType

LOGGER = get_logger("blinky.learn.mastery")


def calculate_attempt_outcome(
    attempt: Attempt,
    question: Question,
    classified_error: Optional[ErrorType] = None,
) -> float:
    """
    Computes deterministic numeric outcome in [0.0, 1.0] for a student attempt (§5.3).
    Includes guess discounting for low confidence and careless mistake weighting.
    """
    if attempt.is_correct:
        outcome = 1.0
        # Guess discount: correct MCQ with confidence = 1 (low)
        if question.type == QuestionType.mcq and attempt.confidence == 1:
            outcome = min(outcome, GUESS_DISCOUNT_CAP)
            LOGGER.info("Applied guess discount to low-confidence correct answer: outcome=%.2f", outcome)
        # Explain question answered with no reasoning text
        elif question.type == QuestionType.explain and not (attempt.reasoning_text or "").strip():
            outcome = min(outcome, GUESS_DISCOUNT_CAP)
            LOGGER.info("Applied guess discount to unreasoned explanation question: outcome=%.2f", outcome)
        return outcome

    # Wrong answer
    if classified_error == ErrorType.careless_mistake:
        # Careless mistake: apply wrong outcome at half weight (outcome = 0.5)
        LOGGER.info("Careless mistake detected: applying wrong outcome at half penalty weight (0.50)")
        return CARELESS_MISTAKE_WEIGHT

    return 0.0


def compute_consistency(outcomes: List[float]) -> float:
    """
    Computes consistency = 1 - stddev(last_outcomes), guarded for n < 2 (§5.3).
    Returns value in [0.0, 1.0].
    """
    n = len(outcomes)
    if n < 2:
        return 1.0

    mean = sum(outcomes) / n
    variance = sum((x - mean) ** 2 for x in outcomes) / (n - 1)
    stddev = math.sqrt(variance)

    consistency = max(0.0, min(1.0, 1.0 - stddev))
    return round(consistency, 3)


def determine_mastery_band(
    mastery: float,
    attempts: int,
    has_transfer_success: bool,
    consistency: float,
) -> MasteryBand:
    """
    Determines per-concept mastery band (§5.3):
    - insufficient_evidence: attempts < 2
    - weak: mastery < 0.40
    - moderate: 0.40 - 0.74 (or >= 0.75 without transfer check / consistency)
    - strong: mastery >= 0.75 AND attempts >= 2 AND has_transfer_success AND consistency >= 0.60
    """
    if attempts < 2:
        return MasteryBand.insufficient_evidence

    if mastery < BAND_WEAK_MAX:
        return MasteryBand.weak

    if mastery >= BAND_STRONG_MIN:
        if (
            attempts >= STRONG_MIN_ATTEMPTS
            and has_transfer_success
            and consistency >= STRONG_MIN_CONSISTENCY
        ):
            return MasteryBand.strong
        # Needs transfer check or higher consistency to claim Strong
        return MasteryBand.moderate

    return MasteryBand.moderate


def update_mastery(
    current_mastery: Mastery,
    attempt: Attempt,
    question: Question,
    classified_error: Optional[ErrorType] = None,
    is_transfer_question: bool = False,
) -> Mastery:
    """
    Executes purely deterministic mastery update (§5.3). No AI calls.
    mastery <- mastery + alpha * (outcome - mastery)
    where alpha = 0.30 * difficulty_weight.
    """
    outcome = calculate_attempt_outcome(attempt, question, classified_error)

    difficulty_wt = DIFFICULTY_WEIGHTS.get(question.difficulty, 1.0)
    alpha = ALPHA_BASE * difficulty_wt

    old_mastery = current_mastery.mastery
    new_mastery = old_mastery + alpha * (outcome - old_mastery)
    new_mastery = max(0.0, min(1.0, round(new_mastery, 4)))

    new_attempts = current_mastery.attempts + 1
    new_correct = current_mastery.correct + (1 if attempt.is_correct else 0)
    new_consecutive = (current_mastery.consecutive_correct + 1) if attempt.is_correct else 0

    # Track last 5 outcomes
    outcomes = list(current_mastery.last_outcomes) + [outcome]
    if len(outcomes) > 5:
        outcomes = outcomes[-5:]

    consistency = compute_consistency(outcomes)

    # Transfer success requires answering a transfer item correctly
    has_transfer = current_mastery.has_transfer_success or (is_transfer_question and attempt.is_correct)

    band = determine_mastery_band(
        mastery=new_mastery,
        attempts=new_attempts,
        has_transfer_success=has_transfer,
        consistency=consistency,
    )

    return Mastery(
        student_id=current_mastery.student_id,
        concept_id=current_mastery.concept_id,
        mastery=new_mastery,
        attempts=new_attempts,
        correct=new_correct,
        consecutive_correct=new_consecutive,
        last_outcomes=outcomes,
        has_transfer_success=has_transfer,
        consistency=consistency,
        band=band,
        updated_at=attempt.created_at,
    )

