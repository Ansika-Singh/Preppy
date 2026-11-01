import shutil
import tempfile
from pathlib import Path

import pytest

from learn.config import SM2_INITIAL_EASE, SM2_MAX_EASE, SM2_MIN_EASE
from learn.db import LearnDB
from learn.revision import (
    REASON_TEMPLATES,
    build_explanation_string,
    get_revision_quiz,
    schedule_concept_revision,
)
from learn.schemas import (
    Concept,
    Mastery,
    MasteryBand,
    Question,
    RevisionItem,
)


@pytest.fixture
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_file = Path(tmp_dir) / "test_learn.db"
    db = LearnDB(db_path=db_file)
    yield db
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestAdaptiveRevisionEngine:
    """Rigorous tests for deterministic SM-2 revision and explanation generation (§5.4)."""

    def test_sm2_transition_table_success_progression(self):
        concept = Concept(id="c1", material_id="m1", name="Newton's First Law")
        now = 100000

        # Attempt 1: First success (consecutive_correct = 1) -> interval = 1
        m1 = Mastery(concept_id="c1", mastery=0.65, attempts=1, correct=1, consecutive_correct=1, consistency=1.0, band=MasteryBand.moderate)
        r1 = schedule_concept_revision(concept, None, m1, outcome=1.0, now=now)
        assert r1.interval_days == 1
        assert r1.ease == round(SM2_INITIAL_EASE + 0.05, 3)  # 2.35
        assert r1.due_at == now + 86400

        # Attempt 2: Second success (consecutive_correct = 2) -> interval = 3
        m2 = Mastery(concept_id="c1", mastery=0.75, attempts=2, correct=2, consecutive_correct=2, consistency=1.0, band=MasteryBand.moderate)
        r2 = schedule_concept_revision(concept, r1, m2, outcome=1.0, now=now)
        assert r2.interval_days == 3
        assert r2.ease == round(2.35 + 0.05, 3)  # 2.40
        assert r2.due_at == now + (3 * 86400)

        # Attempt 3: Third success (consecutive_correct = 3) -> round(3 * 2.40) = 7
        m3 = Mastery(concept_id="c1", mastery=0.85, attempts=3, correct=3, consecutive_correct=3, consistency=1.0, band=MasteryBand.moderate)
        r3 = schedule_concept_revision(concept, r2, m3, outcome=1.0, now=now)
        assert r3.interval_days == 7
        assert r3.ease == round(2.40 + 0.05, 3)  # 2.45
        assert r3.due_at == now + (7 * 86400)

    def test_sm2_transition_table_partial_outcome(self):
        concept = Concept(id="c1", material_id="m1", name="Friction")
        now = 100000
        prev_item = RevisionItem(concept_id="c1", due_at=now, interval_days=6, ease=2.40)

        # 0.4 <= outcome < 0.8: interval = round(6 * 0.6) = 4, ease -= 0.05
        m = Mastery(concept_id="c1", mastery=0.55, attempts=3, consecutive_correct=0, consistency=0.8, band=MasteryBand.moderate)
        r = schedule_concept_revision(concept, prev_item, m, outcome=0.50, now=now)

        assert r.interval_days == 4
        assert r.ease == 2.35
        assert r.reason_code == "LAPSE_AFTER_SUCCESS"

    def test_sm2_transition_table_wrong_and_open_misconception(self):
        concept = Concept(id="c1", material_id="m1", name="Inertia")
        now = 100000
        prev_item = RevisionItem(concept_id="c1", due_at=now, interval_days=8, ease=2.40)

        # Wrong answer with open misconception -> interval = 1, due_at = today (now), ease -= 0.20
        m = Mastery(concept_id="c1", mastery=0.35, attempts=4, consecutive_correct=0, consistency=0.6, band=MasteryBand.weak)
        r = schedule_concept_revision(concept, prev_item, m, outcome=0.0, has_open_misconception=True, now=now)

        assert r.interval_days == 1
        assert r.ease == 2.20
        assert r.due_at == now  # Due today
        assert r.reason_code == "OPEN_MISCONCEPTION"
        assert "unresolved conceptual misunderstanding" in r.reason_text

    def test_inconsistency_cap(self):
        concept = Concept(id="c1", material_id="m1", name="Momentum")
        now = 100000
        prev_item = RevisionItem(concept_id="c1", due_at=now, interval_days=8, ease=2.40)

        # Inconsistency < 0.50 -> interval capped at 2
        m = Mastery(concept_id="c1", mastery=0.65, attempts=4, consecutive_correct=3, consistency=0.35, band=MasteryBand.moderate)
        r = schedule_concept_revision(concept, prev_item, m, outcome=1.0, now=now)

        assert r.interval_days <= 2
        assert r.reason_code == "INCONSISTENT_RECENT"
        assert "inconsistent understanding" in r.reason_text

    def test_mastery_band_adjustments(self):
        concept = Concept(id="c1", material_id="m1", name="Kinematics")
        now = 100000
        prev_item = RevisionItem(concept_id="c1", due_at=now, interval_days=10, ease=2.50)

        # Weak band: interval capped at 3
        m_weak = Mastery(concept_id="c1", mastery=0.30, attempts=3, consecutive_correct=1, consistency=0.8, band=MasteryBand.weak)
        r_weak = schedule_concept_revision(concept, prev_item, m_weak, outcome=0.50, now=now)
        assert r_weak.interval_days <= 3
        assert r_weak.reason_code == "WEAK_MASTERY"

        # Strong band: interval multiplied by 1.2
        m_strong = Mastery(concept_id="c1", mastery=0.90, attempts=5, consecutive_correct=4, has_transfer_success=True, consistency=0.9, band=MasteryBand.strong)
        r_strong = schedule_concept_revision(concept, prev_item, m_strong, outcome=1.0, now=now)
        # Prev interval 10 * ease 2.50 = 25 -> 25 * 1.2 = 30
        assert r_strong.interval_days == 30

    def test_explanation_string_templates(self):
        """Verifies each template string is correctly formatted (§5.4)."""
        for code in REASON_TEMPLATES.keys():
            text = build_explanation_string(code, "Newton's Second Law", mastery=0.45, consistency=0.72)
            assert "Newton's Second Law" in text
            assert len(text) > 20

    def test_determinism_same_inputs_same_outputs(self):
        """Verification that the scheduler is 100% deterministic with zero network dependency."""
        concept = Concept(id="c_det", material_id="m1", name="Determinism Concept")
        m = Mastery(concept_id="c_det", mastery=0.70, attempts=2, correct=1, consecutive_correct=1, consistency=0.85, band=MasteryBand.moderate)
        item = RevisionItem(concept_id="c_det", due_at=50000, interval_days=3, ease=2.30)

        res_a = schedule_concept_revision(concept, item, m, outcome=1.0, now=60000)
        res_b = schedule_concept_revision(concept, item, m, outcome=1.0, now=60000)

        assert res_a.model_dump() == res_b.model_dump()

    def test_revision_quiz_generation(self, temp_db):
        from learn.schemas import Material, MaterialKind
        mat = Material(id="mat_1", title="Rotational Motion", kind=MaterialKind.notes, content_hash="h", okf_text="Sample text.")
        temp_db.save_material(mat)
        concept = Concept(id="c_rev", material_id="mat_1", name="Torque")
        temp_db.save_concepts([concept])
        q = Question(id="q_rev", concept_id="c_rev", stem="What is torque?", correct_answer="Rotational force")
        temp_db.save_questions([q])

        # Save an item due today
        due_item = RevisionItem(
            student_id="local",
            concept_id="c_rev",
            due_at=int(100),  # In the past -> due
            interval_days=1,
            ease=2.30,
            reason_code="SPACED_INTERVAL_DUE",
            reason_text="Scheduled review",
        )
        temp_db.save_revision_item(due_item)

        quiz = get_revision_quiz(db=temp_db, student_id="local")
        assert quiz["due_count"] >= 1
        assert len(quiz["items"]) >= 1
        assert quiz["items"][0]["concept_name"] == "Torque"
        assert quiz["items"][0]["question"]["stem"] == "What is torque?"
