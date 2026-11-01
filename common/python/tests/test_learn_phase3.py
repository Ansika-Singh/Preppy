import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from learn.config import DEFAULT_MAX_CONCEPTS_PER_MATERIAL, DEFAULT_MAX_CONCEPT_DEPTH
from learn.concepts import (
    ExtractedConceptItem,
    ExtractedConceptsResponse,
    _post_process_concepts,
    extract_concepts_from_material,
    extract_concepts_offline,
)
from learn.db import LearnDB
from learn.ingest import ingest_document, verify_span_in_material
from learn.llm import LLMClient, LearnNoProviderError
from learn.schemas import MaterialKind, MasteryBand


@pytest.fixture
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_file = Path(tmp_dir) / "test_learn.db"
    db = LearnDB(db_path=db_file)
    yield db
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestIngestionAndSpanVerification:
    """Verifies that ingestion correctly processes documents and validates source spans."""

    def test_ingest_notes_document(self, temp_db):
        text_content = """# Classical Mechanics
Newton's second law of motion states that the acceleration of an object is directly proportional
to the net force acting on it and inversely proportional to its mass. The vector equation is F = ma."""

        mat = ingest_document(
            title="Physics Notes",
            content=text_content,
            kind=MaterialKind.notes,
            file_type="txt",
            db=temp_db,
        )

        assert mat.id.startswith("mat_")
        assert mat.kind == MaterialKind.notes
        assert len(mat.content_hash) == 64
        assert "F = ma" in mat.okf_text

        # Verify saved in DB
        retrieved = temp_db.get_material(mat.id)
        assert retrieved is not None
        assert retrieved.title == "Physics Notes"

    def test_verify_span_substring_success(self):
        mat = ingest_document(
            title="Mechanics",
            content="Force equals mass times acceleration in an inertial frame of reference.",
            kind=MaterialKind.notes,
        )

        # Exact substring
        assert verify_span_in_material(mat, "Force equals mass times acceleration") is True

        # Normalized whitespace / case-insensitive substring
        assert verify_span_in_material(mat, "force  EQUALS mass  times acceleration") is True

    def test_verify_span_substring_rejection(self):
        mat = ingest_document(
            title="Mechanics",
            content="Force equals mass times acceleration.",
            kind=MaterialKind.notes,
        )

        # Fabricated quote not in material must be rejected
        assert verify_span_in_material(mat, "Force is proportional to velocity squared") is False
        assert verify_span_in_material(mat, "") is False


class TestConceptExtractionAndCapping:
    """Tests concept extraction, depth capping, count capping, and syllabus handling."""

    def test_syllabus_honesty_mode(self, temp_db):
        syllabus_text = """# Physics 101 Syllabus
1. Kinematics in one dimension
2. Newton's laws of motion
3. Work and Kinetic Energy
4. Simple Harmonic Motion"""

        mat = ingest_document(
            title="Physics 101 Syllabus",
            content=syllabus_text,
            kind=MaterialKind.syllabus,
            file_type="txt",
            db=temp_db,
        )

        concepts = extract_concepts_offline(mat)
        assert len(concepts) >= 3

        for c in concepts:
            # Syllabus concepts must be marked with syllabus scope
            assert "[Syllabus Scope]" in c.description
            # Syllabus concepts must carry no grounded quotes as facts
            assert len(c.source_spans) == 0

    def test_concept_depth_capped_at_three(self):
        # Construct an artificial 5-level deep hierarchy
        mat = ingest_document(
            title="Deep Hierarchy",
            content="Testing deep hierarchy constraint.",
            kind=MaterialKind.notes,
        )

        raw_items = [
            {"id": "c1", "name": "Level 1", "parent_id": None},
            {"id": "c2", "name": "Level 2", "parent_id": "c1"},
            {"id": "c3", "name": "Level 3", "parent_id": "c2"},
            {"id": "c4", "name": "Level 4", "parent_id": "c3"},
            {"id": "c5", "name": "Level 5", "parent_id": "c4"},
        ]

        concepts = _post_process_concepts(raw_items, mat)
        c_map = {c.id: c for c in concepts}

        # Level 1 has no parent
        assert c_map["c1"].parent_id is None
        # Level 2 parent is c1 (depth 2)
        assert c_map["c2"].parent_id == "c1"
        # Level 3 parent is c2 (depth 3)
        assert c_map["c3"].parent_id == "c2"
        # Level 4 and 5 must have been flattened because depth > 3
        assert c_map["c4"].parent_id is None
        assert c_map["c5"].parent_id is None

    def test_concept_count_capped_at_max(self):
        mat = ingest_document(
            title="Long Topic List",
            content="Testing max concept count.",
            kind=MaterialKind.notes,
        )

        # Generate 40 items
        raw_items = [{"id": f"c_{i}", "name": f"Concept {i}", "parent_id": None} for i in range(40)]
        concepts = _post_process_concepts(raw_items, mat)

        assert len(concepts) == DEFAULT_MAX_CONCEPTS_PER_MATERIAL

    def test_extract_concepts_offline_fallback(self, temp_db):
        content = """# Section 1: Dynamics
- Newton's First Law
- Newton's Second Law
- Newton's Third Law
# Section 2: Energy
- Work-Energy Theorem
- Conservation of Energy"""

        mat = ingest_document(
            title="Physics Notes",
            content=content,
            kind=MaterialKind.notes,
            db=temp_db,
        )

        # Simulate missing AI provider
        mock_llm = LLMClient()
        with patch.object(mock_llm, "generate_structured", side_effect=LearnNoProviderError("No model")):
            concepts = extract_concepts_from_material(mat, llm_client=mock_llm, db=temp_db)

        assert len(concepts) >= 5
        names = [c.name for c in concepts]
        assert "Newton's First Law" in names
        assert "Work-Energy Theorem" in names

        # Verify mastery was automatically initialized
        for c in concepts:
            m = temp_db.get_mastery(c.id)
            assert m is not None
            assert m.mastery == 0.50
            assert m.band == MasteryBand.insufficient_evidence

