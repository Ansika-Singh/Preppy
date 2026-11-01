import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from learn.config import get_call_budget, get_db_path
from learn.db import LearnDB
from learn.llm import (
    LLMClient,
    LearnAIError,
    LearnBudgetExceededError,
    LearnNoProviderError,
    LearnValidationExhaustedError,
)
from learn.schemas import (
    Concept,
    ErrorType,
    Material,
    MaterialKind,
    MisconceptionAnalysis,
    MisconceptionCandidate,
    MisconceptionRecord,
    MisconceptionState,
    Question,
    QuestionType,
    Attempt,
    Mastery,
    MasteryBand,
    Remediation,
    RevisionItem,
    SourceSpan,
)


class TestLearnSchemas:
    """Validates that Preppy Pydantic schemas enforce type safety and constraints."""

    def test_source_span_capping(self):
        long_quote = "A" * 500
        span = SourceSpan(
            material_id="mat_1",
            source_name="physics.pdf",
            quote=long_quote,
            page=2,
        )
        assert len(span.quote) == 300

    def test_question_difficulty_clamping(self):
        q_low = Question(
            id="q_1",
            concept_id="c_1",
            difficulty=0,
            stem="What is F=ma?",
            correct_answer="Newton's Second Law",
        )
        assert q_low.difficulty == 1

        q_high = Question(
            id="q_2",
            concept_id="c_1",
            difficulty=10,
            stem="What is F=ma?",
            correct_answer="Newton's Second Law",
        )
        assert q_high.difficulty == 3

    def test_attempt_confidence_validation(self):
        att = Attempt(
            id="att_1",
            question_id="q_1",
            concept_id="c_1",
            answer_text="Unchanged",
            confidence=4,
            is_correct=False,
        )
        assert att.confidence == 3

    def test_misconception_analysis_schema_valid(self):
        analysis = MisconceptionAnalysis(
            error_type=ErrorType.conceptual_misunderstanding,
            misconception_id="misc_inertial",
            confidence=0.88,
            evidence_quote="mass has not changed so nothing changes",
            rationale="Student ignores applied force relationship.",
            needs_probe=False,
        )
        assert analysis.error_type == ErrorType.conceptual_misunderstanding
        assert analysis.confidence == 0.88

    def test_misconception_analysis_schema_invalid_confidence(self):
        with pytest.raises(ValidationError):
            MisconceptionAnalysis(
                error_type=ErrorType.conceptual_misunderstanding,
                confidence=1.5,  # Exceeds 1.0
                rationale="Invalid",
            )


class TestLearnDatabase:
    """Tests SQLite migrations, CRUD, and restart persistence."""

    @pytest.fixture
    def temp_db_path(self):
        tmp_dir = tempfile.mkdtemp()
        db_file = Path(tmp_dir) / "test_learn.db"
        yield db_file
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_fresh_db_migration(self, temp_db_path):
        db = LearnDB(db_path=temp_db_path)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM learn_schema_version;")
            rows = cursor.fetchall()
            assert len(rows) == 2
            assert max(r[0] for r in rows) == 2

    def test_idempotent_migration(self, temp_db_path):
        db = LearnDB(db_path=temp_db_path)
        # Calling migrate a second time must succeed without errors
        db.migrate()
        db.migrate()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM learn_schema_version;")
            assert cursor.fetchone()[0] == 2

    def test_persistence_across_restart(self, temp_db_path):
        # Session 1: Create and populate DB
        db1 = LearnDB(db_path=temp_db_path)
        mat = Material(
            id="mat_newton",
            student_id="local",
            title="Newtonian Mechanics",
            kind=MaterialKind.notes,
            content_hash="hash_123",
            okf_text="### SOURCE: newton.txt\nForce equals mass times acceleration.",
            created_at=1000,
        )
        db1.save_material(mat)

        concept = Concept(
            id="c_newton2",
            material_id="mat_newton",
            name="Newton's Second Law",
            description="F=ma relation",
            order_idx=1,
            prerequisites=["c_newton1"],
            source_spans=[
                SourceSpan(
                    material_id="mat_newton",
                    source_name="newton.txt",
                    quote="Force equals mass times acceleration.",
                )
            ],
        )
        db1.save_concepts([concept])

        mastery = Mastery(
            student_id="local",
            concept_id="c_newton2",
            mastery=0.72,
            attempts=3,
            correct=2,
            consecutive_correct=1,
            last_outcomes=[1.0, 0.0, 1.0],
            has_transfer_success=True,
            consistency=0.82,
            band=MasteryBand.moderate,
        )
        db1.save_mastery(mastery)

        # Simulate App Restart by destroying connection and initializing fresh instance
        del db1

        db2 = LearnDB(db_path=temp_db_path)
        loaded_mat = db2.get_material("mat_newton")
        assert loaded_mat is not None
        assert loaded_mat.title == "Newtonian Mechanics"

        concepts = db2.list_concepts("mat_newton")
        assert len(concepts) == 1
        assert concepts[0].name == "Newton's Second Law"
        assert len(concepts[0].source_spans) == 1
        assert concepts[0].source_spans[0].quote == "Force equals mass times acceleration."

        loaded_mastery = db2.get_mastery("c_newton2")
        assert loaded_mastery is not None
        assert loaded_mastery.mastery == 0.72
        assert loaded_mastery.has_transfer_success is True
        assert loaded_mastery.last_outcomes == [1.0, 0.0, 1.0]


class TestLearnLLMClient:
    """Tests LLM wrapper, schema validation, retries, and call budget."""

    def test_call_budget_enforcement(self):
        client = LLMClient(budget=2)
        assert client.remaining_budget == 2
        assert client.used_budget == 0

        with patch.object(client, "_call_raw_provider", return_value='{"error_type":"careless_mistake","confidence":0.9,"rationale":"Fast slip","needs_probe":false}'):
            # Call 1
            client.generate_structured(
                prompt_name="misconception_analysis",
                template_args={"concept_name": "Test", "concept_description": "Desc", "grounding_context": "", "candidate_misconceptions": "", "question_stem": "", "correct_answer": "", "student_answer": "", "distractor_hint": "", "reasoning_text": "", "confidence": "2", "time_ms": "1000"},
                schema=MisconceptionAnalysis,
            )

        # Decrement manually to simulate budget consumption
        client.used_budget = 2
        assert client.remaining_budget == 0

        with pytest.raises(LearnBudgetExceededError):
            client._call_raw_provider("test prompt")

    def test_structured_retry_on_invalid_json(self):
        client = LLMClient(budget=10)

        # First attempt returns invalid markdown string; second attempt returns valid JSON
        responses = [
            "Here is the result: not valid json at all",
            '{"error_type":"calculation_error","confidence":0.92,"rationale":"Arithmetic slip","needs_probe":false}',
        ]

        with patch.object(client, "_call_raw_provider", side_effect=responses):
            result = client.generate_structured(
                prompt_name="misconception_analysis",
                template_args={"concept_name": "Test", "concept_description": "Desc", "grounding_context": "", "candidate_misconceptions": "", "question_stem": "", "correct_answer": "", "student_answer": "", "distractor_hint": "", "reasoning_text": "", "confidence": "2", "time_ms": "1000"},
                schema=MisconceptionAnalysis,
                max_retries=2,
            )
            assert result.error_type == ErrorType.calculation_error
            assert result.confidence == 0.92

    def test_structured_exhaustion_raises_error(self):
        client = LLMClient(budget=10)

        # All attempts return invalid JSON
        responses = [
            "Attempt 0 invalid",
            "Attempt 1 invalid",
            "Attempt 2 invalid",
        ]

        with patch.object(client, "_call_raw_provider", side_effect=responses):
            with pytest.raises(LearnValidationExhaustedError):
                client.generate_structured(
                    prompt_name="misconception_analysis",
                    template_args={"concept_name": "Test", "concept_description": "Desc", "grounding_context": "", "candidate_misconceptions": "", "question_stem": "", "correct_answer": "", "student_answer": "", "distractor_hint": "", "reasoning_text": "", "confidence": "2", "time_ms": "1000"},
                    schema=MisconceptionAnalysis,
                    max_retries=2,
                )

