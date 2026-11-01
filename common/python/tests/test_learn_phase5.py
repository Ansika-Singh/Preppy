import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from learn.db import LearnDB
from learn.evaluate_golden import evaluate_provider_on_golden
from learn.golden_dataset import GOLDEN_TEST_CASES
from learn.llm import LLMClient
from learn.misconception import (
    analyze_misconception,
    generate_remediation,
    run_misconception_pipeline,
)
from learn.schemas import (
    Attempt,
    Concept,
    ErrorType,
    Material,
    MaterialKind,
    MisconceptionAnalysis,
    MisconceptionState,
    Question,
    QuestionType,
    Remediation,
    SourceSpan,
)


@pytest.fixture
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_file = Path(tmp_dir) / "test_learn.db"
    db = LearnDB(db_path=db_file)
    yield db
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestMisconceptionEngine:
    """Rigorous tests for Preppy's Priority Misconception Engine (§5.2)."""

    def test_newton_worked_example_end_to_end(self, temp_db):
        """Tests the exact canonical worked example required in §5.2."""
        mat = Material(
            id="mat_newton",
            title="Newtonian Physics",
            kind=MaterialKind.notes,
            content_hash="h1",
            okf_text="### SOURCE: newton.txt\nNewton's second law: F = m*a. Acceleration is directly proportional to net force.",
        )
        temp_db.save_material(mat)

        concept = Concept(
            id="c_n2",
            material_id=mat.id,
            name="Newton's Second Law",
            description="Relationship between force, mass, and acceleration.",
            source_spans=[
                SourceSpan(
                    material_id=mat.id,
                    source_name="newton.txt",
                    quote="Acceleration is directly proportional to net force.",
                )
            ],
        )
        temp_db.save_concepts([concept])

        question = Question(
            id="q_n2",
            concept_id=concept.id,
            type=QuestionType.mcq,
            stem="What happens to acceleration when force doubles at constant mass?",
            options=["Doubles", "Halves", "Unchanged", "Zero"],
            correct_answer="Doubles",
            distractor_map={
                "Unchanged": "Belief that acceleration depends strictly on mass",
            },
        )
        temp_db.save_questions([question])

        # Student answers 'Unchanged' with reasoning 'mass hasn't changed so nothing changes'
        attempt = Attempt(
            id="att_n2",
            question_id=question.id,
            concept_id=concept.id,
            answer_text="Unchanged",
            selected_option="Unchanged",
            reasoning_text="mass hasn't changed so nothing changes",
            confidence=3,
            time_ms=8500,
            is_correct=False,
            score=0.0,
        )
        temp_db.save_attempt(attempt)

        # Mock LLM returning accurate analysis and remediation
        mock_analysis = MisconceptionAnalysis(
            error_type=ErrorType.conceptual_misunderstanding,
            new_misconception_label="acceleration depends only on mass",
            confidence=0.88,
            evidence_quote="mass hasn't changed so nothing changes",
            rationale="Student ignores applied net force variation.",
            needs_probe=False,
        )

        mock_client = LLMClient()
        with patch.object(mock_client, "generate_structured") as mock_gen:
            # First call: analyze_misconception -> returns mock_analysis
            # Second call: generate_remediation -> returns Remediation
            fol_q = Question(
                id="q_fol",
                concept_id=concept.id,
                type=QuestionType.mcq,
                stem="If mass is doubled while force is kept constant, what happens to acceleration?",
                options=["Halves", "Doubles", "Unchanged", "Quadruples"],
                correct_answer="Halves",
            )
            mock_remed = Remediation(
                why_wrong="Acceleration is determined by both force AND mass.",
                core_idea="Newton's 2nd Law states a = F/m. When force doubles, acceleration must double.",
                analogy="Pushing a shopping trolley twice as hard makes it accelerate twice as fast.",
                followup_question=fol_q,
            )
            mock_gen.side_effect = [mock_analysis, mock_remed]

            result = run_misconception_pipeline(
                attempt=attempt,
                question=question,
                concept=concept,
                material=mat,
                db=temp_db,
                llm_client=mock_client,
                loop_count=1,
            )

        assert result["error_type"] == "conceptual_misunderstanding"
        # Two signals (distractor map + verified quote) -> CONFIRMED
        assert result["state"] == "confirmed"
        assert result["evidence_quote"] == "mass hasn't changed so nothing changes"
        assert "trolley" in result["analogy"].lower()
        assert result["followup_question"]["stem"] != question.stem
        assert result["source_label"] == "From your notes (verified)"

        # Verify persisted record in DB
        records = temp_db.list_open_misconceptions()
        assert len(records) == 1
        assert records[0]["concept_id"] == concept.id
        assert records[0]["state"] == "confirmed"

    def test_evidence_quote_verification_discards_hallucination(self, temp_db):
        """Fabricated quotes must be discarded and downgraded to uncertain (§5.2 Step 4)."""
        mat = Material(id="m1", title="Notes", kind=MaterialKind.notes, content_hash="h", okf_text="Sample text.")
        concept = Concept(id="c1", material_id="m1", name="Kinematics")
        question = Question(id="q1", concept_id="c1", stem="Stem", correct_answer="Ans")
        attempt = Attempt(
            id="a1",
            question_id="q1",
            concept_id="c1",
            answer_text="Wrong option",
            reasoning_text="Just guessed it quickly",
            confidence=2,
            is_correct=False,
        )

        # Model hallucinates a quote not present in student's reasoning
        hallucinated_analysis = MisconceptionAnalysis(
            error_type=ErrorType.conceptual_misunderstanding,
            new_misconception_label="Fabricated flaw",
            confidence=0.85,
            evidence_quote="I believe velocity causes acceleration always",  # NOT in student text!
            rationale="Hallucinated",
            needs_probe=False,
        )

        mock_client = LLMClient()
        with patch.object(mock_client, "generate_structured", return_value=hallucinated_analysis):
            analysis, state = analyze_misconception(
                attempt=attempt,
                question=question,
                concept=concept,
                material=mat,
                db=temp_db,
                llm_client=mock_client,
            )

        # Must discard quote and downgrade to uncertain
        assert analysis.evidence_quote is None
        assert analysis.error_type == ErrorType.uncertain
        assert state == MisconceptionState.uncertain
        assert analysis.needs_probe is True

    def test_two_signal_confirmation_rule(self, temp_db):
        """Tests that conceptual_misunderstanding requires 2 independent signals for 'confirmed' (§5.2)."""
        mat = Material(id="m1", title="Notes", kind=MaterialKind.notes, content_hash="h", okf_text="Sample text.")
        concept = Concept(id="c1", material_id="m1", name="Dynamics")
        question_with_distractor = Question(
            id="q1",
            concept_id="c1",
            stem="Stem",
            options=["A", "B", "C", "D"],
            correct_answer="A",
            distractor_map={"B": "Mapped Distractor Misconception"},
        )
        attempt_distractor_only = Attempt(
            id="a1",
            question_id="q1",
            concept_id="c1",
            answer_text="B",
            selected_option="B",
            reasoning_text="",  # No reasoning
            confidence=2,
            is_correct=False,
        )

        # Single signal: only distractor matched, no reasoning quote
        analysis_single = MisconceptionAnalysis(
            error_type=ErrorType.conceptual_misunderstanding,
            new_misconception_label="Mapped Distractor Misconception",
            confidence=0.60,
            evidence_quote=None,
            rationale="Distractor matched",
            needs_probe=False,
        )

        mock_client = LLMClient()
        with patch.object(mock_client, "generate_structured", return_value=analysis_single):
            _, state_single = analyze_misconception(
                attempt=attempt_distractor_only,
                question=question_with_distractor,
                concept=concept,
                material=mat,
                db=temp_db,
                llm_client=mock_client,
            )
        assert state_single == MisconceptionState.suspected

        # Two signals: distractor matched AND reasoning quote verified
        attempt_two_signals = Attempt(
            id="a2",
            question_id="q1",
            concept_id="c1",
            answer_text="B",
            selected_option="B",
            reasoning_text="because speed determines force",
            confidence=3,
            is_correct=False,
        )
        analysis_double = MisconceptionAnalysis(
            error_type=ErrorType.conceptual_misunderstanding,
            new_misconception_label="Mapped Distractor Misconception",
            confidence=0.85,
            evidence_quote="speed determines force",
            rationale="Two signals present",
            needs_probe=False,
        )
        with patch.object(mock_client, "generate_structured", return_value=analysis_double):
            _, state_double = analyze_misconception(
                attempt=attempt_two_signals,
                question=question_with_distractor,
                concept=concept,
                material=mat,
                db=temp_db,
                llm_client=mock_client,
            )
        assert state_double == MisconceptionState.confirmed

    def test_verification_loop_escalation_and_cap(self, temp_db):
        """Tests loop escalation styles and loop cap of 3 (§5.2 Step 6)."""
        mat = Material(id="m1", title="Notes", kind=MaterialKind.notes, content_hash="h", okf_text="Sample text.")
        concept = Concept(id="c1", material_id="m1", name="Gravity")
        temp_db.save_material(mat)
        temp_db.save_concepts([concept])
        question = Question(id="q1", concept_id="c1", stem="Stem", correct_answer="Ans")
        temp_db.save_questions([question])
        attempt = Attempt(id="a1", question_id="q1", concept_id="c1", answer_text="W", is_correct=False)
        temp_db.save_attempt(attempt)

        mock_analysis = MisconceptionAnalysis(
            error_type=ErrorType.conceptual_misunderstanding,
            confidence=0.75,
            rationale="Repeat error",
            needs_probe=False,
        )
        mock_client = LLMClient()

        # Loop 1: standard analogy
        with patch.object(mock_client, "generate_structured", return_value=mock_analysis):
            res1 = run_misconception_pipeline(attempt, question, concept, mat, temp_db, mock_client, loop_count=1)
            assert res1["escalation_style"] == "standard_analogy"
            assert res1["exceeded_loop_cap"] is False

        # Loop 2: worked example
        with patch.object(mock_client, "generate_structured", return_value=mock_analysis):
            res2 = run_misconception_pipeline(attempt, question, concept, mat, temp_db, mock_client, loop_count=2)
            assert res2["escalation_style"] == "worked_example"
            assert res2["exceeded_loop_cap"] is False

        # Loop 3: simpler sub-question + exceeded cap
        with patch.object(mock_client, "generate_structured", return_value=mock_analysis):
            res3 = run_misconception_pipeline(attempt, question, concept, mat, temp_db, mock_client, loop_count=3)
            assert res3["escalation_style"] == "simpler_sub_question"
            assert res3["exceeded_loop_cap"] is True

    def test_golden_dataset_evaluation_mocked_provider(self, temp_db):
        """Runs the 12-item golden misconception evaluation (§6.4) with mocked provider."""
        mock_client = LLMClient(budget=100)

        # For each golden test case, return appropriate expected analysis
        def mock_generate_structured(prompt_name, template_args, schema, **kwargs):
            stem = template_args.get("question_stem", "")
            student_ans = template_args.get("student_answer", "")
            reasoning = template_args.get("reasoning_text", "")

            # Match against golden cases
            for case in GOLDEN_TEST_CASES:
                if case["student_answer"].lower() in student_ans.lower() or case["concept"].lower() in stem.lower():
                    quote = case["expected_quote_sub"] if case["expected_quote_sub"] and case["expected_quote_sub"] in reasoning.lower() else None
                    return MisconceptionAnalysis(
                        error_type=case["expected_error_type"],
                        confidence=0.85 if case["expected_error_type"] != ErrorType.uncertain else 0.40,
                        evidence_quote=quote,
                        rationale="Golden evaluation response",
                        needs_probe=case["expected_error_type"] == ErrorType.uncertain,
                    )
            return MisconceptionAnalysis(
                error_type=ErrorType.uncertain,
                confidence=0.40,
                rationale="Unmatched case",
                needs_probe=True,
            )

        with patch.object(mock_client, "generate_structured", side_effect=mock_generate_structured):
            summary = evaluate_provider_on_golden(mock_client, db=temp_db, verbose=True)

        assert summary["total_cases"] == 12
        assert summary["valid_json_rate"] == 1.0  # 100% JSON valid
        assert summary["classification_accuracy"] >= 0.80  # High accuracy on golden set
        assert summary["valid_quotes_rate"] == 1.0  # All quotes are verbatim
