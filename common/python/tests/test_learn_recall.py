from __future__ import annotations

import pytest
import shutil
import tempfile
import time
from pathlib import Path

from learn.config import (
    PEEKED_COVERAGE_CAP,
    RECITED_COVERAGE_CAP,
    RECITATION_TRIGRAM_THRESHOLD,
)
from learn.db import LearnDB
from learn.recall import (
    calculate_recitation_ratio,
    chunk_document_into_paragraphs,
    extract_chunk_key_ideas,
    verify_exact_substring,
    analyze_recall_transcript,
)
from learn.schemas import (
    Chunk,
    ChunkKeyIdea,
    Concept,
    Material,
    MaterialKind,
    RecallStatus,
    SourceSpan,
)


@pytest.fixture
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_file = Path(tmp_dir) / "test_recall.db"
    db = LearnDB(db_path=db_file)
    yield db
    shutil.rmtree(tmp_dir, ignore_errors=True)


SAMPLE_TEXT = """Newton's first law of motion states that an object at rest will stay at rest, and an object in motion will stay in motion with a constant velocity, unless acted upon by a net external force. This property of matter to resist changes in its state of motion is called inertia. The mass of an object is a direct measure of its inertia: greater mass means greater resistance to changes in motion.

Newton's second law of motion states that the acceleration of an object is directly proportional to the net force acting upon it and inversely proportional to its mass. Mathematically, this is expressed as F_net = m * a. Importantly, if the net force acting on an object is zero, the acceleration is zero, and the velocity remains strictly constant.

Newton's third law of motion asserts that for every action, there is an equal and opposite reaction. When object A exerts a force on object B, object B simultaneously exerts an equal and opposite force on object A. These action-reaction pairs act on different bodies and therefore never cancel each other out."""


def test_chunking_paragraphs():
    chunks = chunk_document_into_paragraphs(SAMPLE_TEXT, material_id="mat_physics")
    assert len(chunks) >= 2
    for i, c in enumerate(chunks):
        assert c.idx == i
        assert c.material_id == "mat_physics"
        assert c.word_count > 30


def test_recitation_ratio_calculation():
    para = "The net force acting on an object causes an immediate acceleration inversely proportional to mass."
    # Verbatim recitation
    recited = "The net force acting on an object causes an immediate acceleration inversely proportional to mass."
    ratio_recited = calculate_recitation_ratio(recited, para)
    assert ratio_recited >= 0.90
    assert ratio_recited > RECITATION_TRIGRAM_THRESHOLD

    # Paraphrased in student's own words
    paraphrased = "When you push something with more power, it speeds up faster, but heavier objects speed up much slower."
    ratio_paraphrased = calculate_recitation_ratio(paraphrased, para)
    assert ratio_paraphrased < 0.20
    assert ratio_paraphrased < RECITATION_TRIGRAM_THRESHOLD


def test_verify_exact_substring():
    text = "The acceleration is directly proportional to the net force."
    # Exact
    assert verify_exact_substring("directly proportional", text) == "directly proportional"
    # Case insensitive should return exact slice from original
    assert verify_exact_substring("DIRECTLY PROPORTIONAL", text) == "directly proportional"
    # Hallucinated
    assert verify_exact_substring("velocity is exponential", text) is None


def test_analyze_recall_too_short():
    chunk = Chunk(
        id="c1",
        material_id="m1",
        idx=0,
        text=SAMPLE_TEXT[:300],
        word_count=50,
        key_ideas=[
            ChunkKeyIdea(id="ki1", claim="Objects stay at rest without net force", supporting_quote="stay at rest"),
        ],
    )
    session, analysis = analyze_recall_transcript(
        chunk=chunk,
        transcript_raw="I think it was about rest.",
        transcript_final="I think it was about rest.",
        peeked=False,
    )
    assert analysis.is_too_short is True
    assert analysis.coverage_score == 0.0
    assert "Too brief" in analysis.summary


def test_analyze_recall_recitation_cap():
    chunk_text = "Newton's first law of motion states that an object at rest will stay at rest, and an object in motion will stay in motion with a constant velocity, unless acted upon by a net external force. This property of matter to resist changes in its state of motion is called inertia."
    chunk = Chunk(
        id="c1",
        material_id="m1",
        idx=0,
        text=chunk_text,
        word_count=45,
        key_ideas=[
            ChunkKeyIdea(id="ki1", claim="An object at rest stays at rest unless acted upon by force", supporting_quote="object at rest will stay at rest"),
            ChunkKeyIdea(id="ki2", claim="Inertia is resistance to change in motion", supporting_quote="resist changes in its state of motion is called inertia"),
        ],
    )
    # Reciting verbatim text
    session, analysis = analyze_recall_transcript(
        chunk=chunk,
        transcript_raw=chunk_text,
        transcript_final=chunk_text,
        peeked=False,
    )
    assert analysis.is_recited is True
    # Coverage must be capped at RECITED_COVERAGE_CAP (0.50)
    assert analysis.coverage_score <= RECITED_COVERAGE_CAP


def test_analyze_recall_peeked_cap():
    chunk_text = "The acceleration of an object is directly proportional to the net force acting upon it and inversely proportional to its mass."
    chunk = Chunk(
        id="c2",
        material_id="m1",
        idx=1,
        text=chunk_text,
        word_count=20,
        key_ideas=[
            ChunkKeyIdea(id="ki1", claim="Acceleration is proportional to net force", supporting_quote="directly proportional to the net force"),
            ChunkKeyIdea(id="ki2", claim="Acceleration is inversely proportional to mass", supporting_quote="inversely proportional to its mass"),
        ],
    )
    # Paraphrased with peeked=True
    recall_words = "Basically, whenever a net force acts on an object, its acceleration is proportional to that net force, and inversely proportional to the mass."
    session, analysis = analyze_recall_transcript(
        chunk=chunk,
        transcript_raw=recall_words,
        transcript_final=recall_words,
        peeked=True,
    )
    assert analysis.peeked is True
    assert analysis.coverage_score <= PEEKED_COVERAGE_CAP


def test_contradiction_bridges_to_misconceptions(temp_db):
    # Setup material and concept in DB
    mat = Material(
        id="mat_phys",
        title="Physics Notes",
        kind=MaterialKind.notes,
        content_hash="abc",
        okf_text=SAMPLE_TEXT,
        created_at=int(time.time()),
    )
    temp_db.save_material(mat)

    concept = Concept(
        id="con_newton2",
        material_id="mat_phys",
        name="Newton's Second Law",
        description="F = ma and cause-effect of force on acceleration",
        order_idx=1,
        source_spans=[SourceSpan(material_id="mat_phys", source_name="Physics Notes", quote="F_net = m * a")],
    )
    temp_db.save_concepts([concept])

    chunk = Chunk(
        id="chunk_n2",
        material_id="mat_phys",
        concept_id="con_newton2",
        idx=0,
        text="Newton's second law of motion states that the acceleration of an object is directly proportional to the net force acting upon it and inversely proportional to its mass. Mathematically, this is expressed as F_net = m * a.",
        word_count=35,
        key_ideas=[
            ChunkKeyIdea(id="ki_force_accel", claim="Net force causes acceleration, not velocity", supporting_quote="acceleration of an object is directly proportional to the net force"),
        ],
    )
    temp_db.save_chunk(chunk)

    # Student recall states a direct contradiction
    contradictory_recall = "When a body moves at a constant velocity, there must always be a net force pushing it forward to keep the velocity going."
    session, analysis = analyze_recall_transcript(
        chunk=chunk,
        transcript_raw=contradictory_recall,
        transcript_final=contradictory_recall,
        peeked=False,
        db=temp_db,
    )

    # Session persisted in DB
    saved_session = temp_db.get_recall_session(session.id)
    assert saved_session is not None
    assert saved_session.chunk_id == "chunk_n2"
    assert saved_session.student_id == "local"

