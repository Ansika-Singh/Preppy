from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from .db import LearnDB
from .golden_dataset import GOLDEN_TEST_CASES
from .llm import LLMClient
from .misconception import analyze_misconception
from .schemas import (
    Attempt,
    Concept,
    ErrorType,
    Material,
    MaterialKind,
    Question,
    QuestionType,
)


def evaluate_provider_on_golden(
    client: LLMClient,
    db: Optional[LearnDB] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Evaluates an LLM client or mocked provider on the 12-item Golden Misconception Benchmark (§6.4).
    Reports error-type classification accuracy, JSON validity, and verbatim quote integrity.
    """
    test_db = db or LearnDB(db_path=":memory:")
    total = len(GOLDEN_TEST_CASES)
    valid_json_count = 0
    correct_classification_count = 0
    valid_quotes_count = 0
    results: List[Dict[str, Any]] = []

    for case in GOLDEN_TEST_CASES:
        mat = Material(
            id=f"mat_{case['id']}",
            title=f"Material {case['concept']}",
            kind=MaterialKind.notes,
            content_hash="hash",
            okf_text=f"### SOURCE: {case['concept']}.txt\nGoverning principles of {case['concept']}.",
        )
        test_db.save_material(mat)

        concept = Concept(
            id=f"c_{case['id']}",
            material_id=mat.id,
            name=case["concept"],
            description=f"Core concept {case['concept']}",
        )
        test_db.save_concepts([concept])

        distractor_map = {}
        if case["distractor_hint"]:
            distractor_map[case["student_answer"]] = case["distractor_hint"]

        question = Question(
            id=f"q_{case['id']}",
            concept_id=concept.id,
            type=QuestionType.mcq,
            difficulty=2,
            stem=case["question"],
            options=[case["correct_answer"], case["student_answer"], "Option C", "Option D"],
            correct_answer=case["correct_answer"],
            distractor_map=distractor_map,
        )
        test_db.save_questions([question])

        attempt = Attempt(
            id=f"att_{case['id']}",
            question_id=question.id,
            concept_id=concept.id,
            answer_text=case["student_answer"],
            reasoning_text=case["reasoning"],
            confidence=case["confidence"],
            time_ms=case["time_ms"],
            is_correct=False,
            score=0.0,
        )
        test_db.save_attempt(attempt)

        try:
            analysis, state = analyze_misconception(
                attempt=attempt,
                question=question,
                concept=concept,
                material=mat,
                db=test_db,
                llm_client=client,
            )
            valid_json_count += 1
            is_match = analysis.error_type == case["expected_error_type"]
            if is_match:
                correct_classification_count += 1

            # Check quote validity
            quote = analysis.evidence_quote
            quote_valid = True
            if quote:
                student_full = f"{attempt.answer_text} {attempt.reasoning_text}".lower()
                if quote.lower() not in student_full:
                    quote_valid = False
            if quote_valid:
                valid_quotes_count += 1

            results.append({
                "case_id": case["id"],
                "concept": case["concept"],
                "expected": case["expected_error_type"].value,
                "predicted": analysis.error_type.value,
                "confidence": analysis.confidence,
                "state": state.value,
                "evidence_quote": analysis.evidence_quote,
                "match": is_match,
            })
        except Exception as exc:
            results.append({
                "case_id": case["id"],
                "concept": case["concept"],
                "expected": case["expected_error_type"].value,
                "error": str(exc),
                "match": False,
            })

    accuracy = round(correct_classification_count / total, 3)
    json_rate = round(valid_json_count / total, 3)
    quote_rate = round(valid_quotes_count / total, 3)

    summary = {
        "total_cases": total,
        "valid_json_rate": json_rate,
        "classification_accuracy": accuracy,
        "valid_quotes_rate": quote_rate,
        "correct_classifications": correct_classification_count,
        "results": results,
    }

    if verbose:
        sys.stderr.write(
            f"\n=== Golden Misconception Benchmark Results ===\n"
            f"Accuracy: {accuracy * 100:.1f}% ({correct_classification_count}/{total})\n"
            f"JSON Validity: {json_rate * 100:.1f}%\n"
            f"Quote Verbatim Validity: {quote_rate * 100:.1f}%\n"
        )

    return summary

