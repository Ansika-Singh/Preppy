import shutil
import tempfile
from pathlib import Path

import pytest

from learn.config import GUESS_DISCOUNT_CAP
from learn.db import LearnDB
from learn.diagnosis import (
    start_diagnostic_session,
    submit_diagnostic_answer,
    get_diagnostic_report,
)
from learn.ingest import ingest_document
from learn.concepts import extract_concepts_offline
from learn.mastery import (
    calculate_attempt_outcome,
    compute_consistency,
    determine_mastery_band,
    update_mastery,
)
from learn.questions import validate_question_shape, create_offline_concept_question
from learn.schemas import (
    Attempt,
    Concept,
    ErrorType,
    Mastery,
    MasteryBand,
    MaterialKind,
    Question,
    QuestionType,
)


@pytest.fixture
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_file = Path(tmp_dir) / "test_learn.db"
    db = LearnDB(db_path=db_file)
    yield db
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestDeterministicMastery:
    """Rigorous unit tests for deterministic mastery math and bands (§5.3)."""

    def test_alpha_formula_and_difficulty_weight(self):
        concept = Concept(id="c_diff", material_id="mat_1", name="Difficulty Test")
        base_m = Mastery(concept_id="c_diff", mastery=0.50, attempts=1)

        # Difficulty 2 (weight 1.0 -> alpha = 0.30)
        q2 = Question(id="q2", concept_id="c_diff", difficulty=2, stem="Stem", correct_answer="Ans")
        att_correct = Attempt(id="a1", question_id="q2", concept_id="c_diff", answer_text="Ans", is_correct=True, confidence=3)
        # Expected: 0.50 + 0.30 * (1.0 - 0.50) = 0.65
        res2 = update_mastery(base_m, att_correct, q2)
        assert res2.mastery == 0.65

        # Difficulty 3 (weight 1.2 -> alpha = 0.36)
        q3 = Question(id="q3", concept_id="c_diff", difficulty=3, stem="Stem", correct_answer="Ans")
        # Expected: 0.50 + 0.36 * (1.0 - 0.50) = 0.68
        res3 = update_mastery(base_m, att_correct, q3)
        assert res3.mastery == 0.68

        # Difficulty 1 (weight 0.8 -> alpha = 0.24)
        q1 = Question(id="q1", concept_id="c_diff", difficulty=1, stem="Stem", correct_answer="Ans")
        # Expected: 0.50 + 0.24 * (1.0 - 0.50) = 0.62
        res1 = update_mastery(base_m, att_correct, q1)
        assert res1.mastery == 0.62

    def test_guess_discount_low_confidence(self):
        q = Question(id="q_guess", concept_id="c_1", type=QuestionType.mcq, difficulty=2, stem="Stem", correct_answer="Ans")
        att = Attempt(id="a_guess", question_id="q_guess", concept_id="c_1", answer_text="Ans", is_correct=True, confidence=1)

        outcome = calculate_attempt_outcome(att, q)
        assert outcome == GUESS_DISCOUNT_CAP  # 0.70

    def test_guess_discount_unreasoned_explain(self):
        q = Question(id="q_exp", concept_id="c_1", type=QuestionType.explain, difficulty=2, stem="Stem", correct_answer="Ans")
        att = Attempt(id="a_exp", question_id="q_exp", concept_id="c_1", answer_text="Ans", reasoning_text="", is_correct=True, confidence=3)

        outcome = calculate_attempt_outcome(att, q)
        assert outcome == GUESS_DISCOUNT_CAP  # 0.70

    def test_careless_mistake_half_weight(self):
        q = Question(id="q_careless", concept_id="c_1", difficulty=2, stem="Stem", correct_answer="Ans")
        att = Attempt(id="a_careless", question_id="q_careless", concept_id="c_1", answer_text="Wrong", is_correct=False)

        outcome = calculate_attempt_outcome(att, q, classified_error=ErrorType.careless_mistake)
        assert outcome == 0.50

    def test_transfer_requirement_for_strong_band(self):
        # A high mastery score (0.85) without transfer check must NOT be marked Strong
        band_no_transfer = determine_mastery_band(
            mastery=0.85,
            attempts=3,
            has_transfer_success=False,
            consistency=0.90,
        )
        assert band_no_transfer == MasteryBand.moderate

        # With transfer success + consistency >= 0.60 + attempts >= 2, becomes Strong
        band_with_transfer = determine_mastery_band(
            mastery=0.85,
            attempts=3,
            has_transfer_success=True,
            consistency=0.90,
        )
        assert band_with_transfer == MasteryBand.strong

    def test_insufficient_evidence_and_weak_bands(self):
        # attempts < 2 is insufficient evidence regardless of score
        assert determine_mastery_band(0.95, attempts=1, has_transfer_success=True, consistency=1.0) == MasteryBand.insufficient_evidence
        assert determine_mastery_band(0.20, attempts=1, has_transfer_success=False, consistency=1.0) == MasteryBand.insufficient_evidence

        # attempts >= 2 and mastery < 0.40 is Weak
        assert determine_mastery_band(0.35, attempts=2, has_transfer_success=False, consistency=0.8) == MasteryBand.weak

    def test_consistency_computation(self):
        # n < 2 -> consistency = 1.0
        assert compute_consistency([1.0]) == 1.0

        # Uniform outcomes -> stddev = 0 -> consistency = 1.0
        assert compute_consistency([1.0, 1.0, 1.0]) == 1.0

        # Inconsistent outcomes -> stddev > 0 -> consistency < 1.0
        inconsistent = compute_consistency([1.0, 0.0, 1.0, 0.0])
        assert 0.0 <= inconsistent < 0.60


class TestQuestionsAndDiagnosticSession:
    """Tests question validation and diagnostic assessment flow (§5.1)."""

    def test_validate_question_shape(self):
        valid_q = Question(
            id="qv",
            concept_id="c_1",
            type=QuestionType.mcq,
            stem="What is the net force when acceleration is zero?",
            options=["Zero net force", "Constant force", "Infinite force", "Variable force"],
            correct_answer="Zero net force",
        )
        assert validate_question_shape(valid_q) is True

        # Rejected: fewer than 4 options
        invalid_options = Question(
            id="qi1",
            concept_id="c_1",
            type=QuestionType.mcq,
            stem="Stem here",
            options=["A", "B"],
            correct_answer="A",
        )
        assert validate_question_shape(invalid_options) is False

        # Rejected: correct answer not in options
        missing_ans = Question(
            id="qi2",
            concept_id="c_1",
            type=QuestionType.mcq,
            stem="Stem here",
            options=["A", "B", "C", "D"],
            correct_answer="E",
        )
        assert validate_question_shape(missing_ans) is False

    def test_diagnostic_session_lifecycle(self, temp_db):
        text = """# Dynamics
- Newton's First Law
- Newton's Second Law
- Newton's Third Law"""
        mat = ingest_document(title="Dynamics Notes", content=text, kind=MaterialKind.notes, db=temp_db)
        concepts = extract_concepts_offline(mat)
        temp_db.save_concepts(concepts)

        # Start diagnostic session
        session = start_diagnostic_session(mat.id, db=temp_db, question_count=3)
        assert len(session.question_ids) == 3
        assert session.current_index == 0
        assert session.completed is False

        # Submit answer 1 (correct)
        q1 = temp_db.get_question(session.question_ids[0])
        res1 = submit_diagnostic_answer(
            session_id=session.session_id,
            answer_text=q1.correct_answer,
            selected_option=q1.correct_answer,
            reasoning_text="Direct application of Newton's law",
            confidence=3,
            time_ms=4500,
            db=temp_db,
        )
        assert res1["is_correct"] is True
        assert res1["score"] == 1.0
        assert res1["needs_misconception_analysis"] is False

        # Submit answer 2 (wrong with distractor misconception)
        q2 = temp_db.get_question(session.question_ids[1])
        wrong_opt = [opt for opt in q2.options if opt != q2.correct_answer][0]
        res2 = submit_diagnostic_answer(
            session_id=session.session_id,
            answer_text=wrong_opt,
            selected_option=wrong_opt,
            reasoning_text="I guessed this",
            confidence=1,
            time_ms=2100,
            db=temp_db,
        )
        assert res2["is_correct"] is False
        assert res2["needs_misconception_analysis"] is True

        # Submit answer 3 (to complete session)
        q3 = temp_db.get_question(session.question_ids[2])
        submit_diagnostic_answer(
            session_id=session.session_id,
            answer_text=q3.correct_answer,
            selected_option=q3.correct_answer,
            reasoning_text="Final reasoning",
            confidence=2,
            time_ms=3000,
            db=temp_db,
        )

        # Check diagnostic report
        report = get_diagnostic_report(session.session_id, db=temp_db)
        assert report["completed"] is True
        assert report["total_answered"] == 3
        assert report["correct_answers"] == 2
        assert len(report["concept_results"]) >= 2

