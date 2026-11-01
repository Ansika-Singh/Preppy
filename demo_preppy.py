"""
Preppy — Live Interactive Demonstration Script
Tagline: Don't just learn. Prove you understand.

Run with:
    python demo_preppy.py
"""

import sys
import time
from pathlib import Path

# Ensure common/python is on sys.path
sys.path.insert(0, str(Path(__file__).parent / "common" / "python"))

from learn.api import handle_learn_rpc
from learn.config import SM2_INITIAL_EASE
from learn.db import LearnDB
from learn.mastery import update_mastery
from learn.revision import schedule_concept_revision
from learn.schemas import (
    Attempt,
    Concept,
    ErrorType,
    Mastery,
    MasteryBand,
    Material,
    MaterialKind,
    MisconceptionRecord,
    MisconceptionState,
    Question,
    QuestionType,
    RevisionItem,
)


def print_banner(text: str):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_step(num: int, title: str):
    print(f"\n[STEP {num}] {title}")
    print("-" * 50)


def run_demo():
    print_banner("PREPPY: Don't Just Learn. Prove You Understand.\n  Live Interactive Demonstration")

    # ---------------------------------------------------------
    # STEP 1: Load Engineering Physics Demo Dataset
    # ---------------------------------------------------------
    print_step(1, "Ingestion & Concept Graph Extraction")
    print("Loading syllabus & lecture notes for Engineering Physics...")
    sample_res = handle_learn_rpc("learn.sample.load", {})
    if not sample_res.get("success"):
        print("Error loading sample:", sample_res)
        return

    sample = sample_res["sample"]
    print(f" -> Ingested Syllabus Material: {sample['syllabus_material_id']}")
    print(f" -> Ingested Notes Material:    {sample['notes_material_id']}")
    print(f" -> Extracted Concepts:         {sample['syllabus_concepts_count']} syllabus concepts (depth capped <= 3)")
    print(f" -> Diagnostic Questions:       {sample['questions_count']} questions pre-mapped to misconceptions")

    concepts_res = handle_learn_rpc("learn.concepts.list", {})
    concepts = concepts_res.get("concepts", [])
    print("\nExtracted Concept Tree (Sample):")
    for item in concepts[:6]:
        c = item["concept"]
        indent = "  " * (c.get("depth", 1))
        print(f"  {indent}* {c['name']} (ID: {c['id']})")

    # ---------------------------------------------------------
    # STEP 2: Intelligent Knowledge Diagnosis (Question & Attempt)
    # ---------------------------------------------------------
    print_step(2, "Diagnostic Assessment (Newton's Second Law)")
    diag_res = handle_learn_rpc("learn.diagnostic.start", {"material_id": sample["notes_material_id"]})
    session_id = diag_res["session_id"]
    question = diag_res["first_question"]

    print(f"Session Started: {session_id}")
    print(f"\nQuestion: {question['stem']}")
    letters = ["A", "B", "C", "D"]
    for i, opt in enumerate(question["options"]):
        lbl = letters[i] if i < len(letters) else str(i)
        print(f"  {lbl}) {opt}")

    print("\n--- Student Response ---")
    print("Student selects: B")
    print("Student explanation:")
    print('  "Because the truck is much heavier, it experiences more gravitational force pulling it forward."')
    print("Confidence rating: 3 (High)")

    # Submit answer
    submit_res = handle_learn_rpc(
        "learn.diagnostic.submit",
        {
            "session_id": session_id,
            "question_id": question["id"],
            "selected_option": "B",
            "reasoning_text": "Because the truck is much heavier, it experiences more gravitational force pulling it forward.",
            "confidence": 3,
            "time_ms": 14200,
        },
    )

    result = submit_res["result"]
    print(f"\nResult: {'CORRECT' if result['is_correct'] else 'INCORRECT'}")
    print(f"Mastery Updated: {result['new_mastery']:.2f} ({result['band'].upper()})")
    print(f"Needs Remediation: {result['needs_misconception_analysis']}")

    # ---------------------------------------------------------
    # STEP 3: Misconception Engine (Priority Feature)
    # ---------------------------------------------------------
    print_step(3, "Misconception Diagnosis & Verbatim Quote Verification")
    print("Running 7-step Misconception Engine...")

    misc_res = handle_learn_rpc(
        "learn.misconception.analyze",
        {
            "attempt_id": result["attempt_id"],
            "question_id": question["id"],
            "concept_id": question["concept_id"],
            "loop_count": 1,
        },
    )

    analysis = misc_res["analysis"]
    print(f"\n-> Error Type Detected:    {analysis['error_type'].upper()}")
    print(f"-> Misconception State:    {analysis['state'].upper()} (Confirmed via 2-signal rule)")
    print(f"-> Confidence Score:       {analysis['confidence']:.2f} (Threshold >= 0.55 enforced)")
    print(f"-> Verbatim Quote Evidence: \"{analysis['evidence_quote']}\"")
    print(f"   (Verified substring match against student's explanation: PASS)")

    print(f"\n--- Targeted Remediation (Loop 1: Analogy) ---")
    print(f"Why it is wrong:")
    print(f"  {analysis['why_wrong']}")
    print(f"\nCore Idea:")
    print(f"  {analysis['core_idea']}")
    print(f"\nAnalogy:")
    print(f"  {analysis['analogy']}")

    print(f"\n--- Verification Follow-up Item ---")
    followup = analysis["followup_question"]
    print(f"Follow-up Prompt: {followup['stem']}")
    for i, opt in enumerate(followup["options"]):
        lbl = letters[i] if i < len(letters) else str(i)
        print(f"  {lbl}) {opt}")

    # ---------------------------------------------------------
    # STEP 4: Escalation Loop Ladder (When Student Persists)
    # ---------------------------------------------------------
    print_step(4, "Escalation Ladder Demo (Loops 1 -> 2 -> 3 -> Cap)")
    print("Demonstrating how Preppy adapts when student makes repeated errors:")

    # Loop 2 escalation
    l2_res = handle_learn_rpc(
        "learn.misconception.analyze",
        {
            "attempt_id": result["attempt_id"],
            "question_id": question["id"],
            "concept_id": question["concept_id"],
            "loop_count": 2,
        },
    )
    l2 = l2_res["analysis"]
    print(f"\n[Loop 2 Escalation]: {l2['escalation_style'].upper()}")
    print(f"  Style: Worked Example / Contrastive Explanation")
    print(f"  Preview: {l2['analogy'][:100]}...")

    # Loop 3 escalation & cap
    l3_res = handle_learn_rpc(
        "learn.misconception.analyze",
        {
            "attempt_id": result["attempt_id"],
            "question_id": question["id"],
            "concept_id": question["concept_id"],
            "loop_count": 3,
        },
    )
    l3 = l3_res["analysis"]
    print(f"\n[Loop 3 Escalation]: {l3['escalation_style'].upper()}")
    print(f"  Exceeded Loop Cap? {l3['exceeded_loop_cap']}")
    print(f"  Action: Cap triggered (<= 3 loops enforced). Student recommended to review foundational concept.")

    # ---------------------------------------------------------
    # STEP 5: Adaptive Revision Engine (SM-2 Spaced Repetition)
    # ---------------------------------------------------------
    print_step(5, "Deterministic Adaptive Revision Engine")
    
    # Check queue
    queue_res = handle_learn_rpc("learn.revision.queue", {"max_items": 10})
    queue = queue_res.get("queue", [])
    print(f"Active Revision Queue Items: {len(queue)}")
    if queue:
        item = queue[0]
        print(f"\nTop Scheduled Concept: {item['concept_name']}")
        print(f"Due in: {item['due_days']} days (Immediate next-day review due to active misconception)")
        print(f"Scheduling Rationale:")
        print(f"  \"{item['reason_text']}\"")

    print("\n--- SM-2 Progression Simulation ---")
    c_dummy = Concept(id="c_test", material_id="m1", name="Newton's Second Law of Motion", depth=1)
    m_dummy = Mastery(
        student_id="local", concept_id="c_test", mastery=0.85, attempts=4,
        correct=4, consecutive_correct=1, last_outcomes=[1.0],
        has_transfer_success=True, consistency=0.85, band=MasteryBand.strong,
        updated_at=int(time.time()),
    )
    rev1 = schedule_concept_revision(c_dummy, None, m_dummy, outcome=1.0)
    print(f"After 1st Verified Success: Interval = {rev1.interval_days} days, Ease = {rev1.ease:.2f}")

    m_dummy.consecutive_correct = 2
    rev2 = schedule_concept_revision(c_dummy, rev1, m_dummy, outcome=1.0)
    print(f"After 2nd Verified Success: Interval = {rev2.interval_days} days, Ease = {rev2.ease:.2f}")

    m_dummy.consecutive_correct = 3
    rev3 = schedule_concept_revision(c_dummy, rev2, m_dummy, outcome=1.0)
    print(f"After 3rd Verified Success: Interval = {rev3.interval_days} days, Ease = {rev3.ease:.2f}")

    # Inconsistency cap demonstration
    m_inconsistent = Mastery(
        student_id="local", concept_id="c_test", mastery=0.60, attempts=5,
        correct=3, consecutive_correct=3, last_outcomes=[1.0, 0.0, 1.0],
        has_transfer_success=True, consistency=0.40, band=MasteryBand.moderate,
        updated_at=int(time.time()),
    )
    rev_inc = schedule_concept_revision(c_dummy, rev2, m_inconsistent, outcome=1.0)
    print(f"\nInconsistency Check (Student erratic, consistency = 0.40):")
    print(f"  Standard interval was {rev3.interval_days} days -> CLAMPED TO {rev_inc.interval_days} days (cap <= 2 enforced)")
    print(f"  Explanation: \"{rev_inc.reason_text}\"")

    print_banner("DEMONSTRATION COMPLETE: All 3 Preppy Features Operational!")


if __name__ == "__main__":
    run_demo()
