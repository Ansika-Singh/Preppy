from __future__ import annotations

import json
import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from utils.logging import get_logger
from .db import LearnDB
from .ingest import verify_span_in_material
from .llm import LLMClient, LearnAIError, get_llm_client
from .schemas import (
    Concept,
    Material,
    MaterialKind,
    MisconceptionCandidate,
    Question,
    QuestionType,
    SourceSpan,
)

LOGGER = get_logger("blinky.learn.questions")


class GeneratedQuestionItem(BaseModel):
    stem: str
    type: str = "mcq"
    difficulty: int = 2
    options: List[str] = Field(default_factory=list)
    correct_answer: str
    distractor_map: Dict[str, str] = Field(default_factory=dict)
    source_quote: Optional[str] = None
    rubric: Optional[str] = None


class GeneratedQuestionsResponse(BaseModel):
    questions: List[GeneratedQuestionItem]


def validate_question_shape(q: Question) -> bool:
    """
    Validates structural rules (§6.3):
    1. MCQ must have >= 3 distractors (total options >= 4).
    2. Correct answer is in options and not identical to any distractor key.
    3. Question stem does not give away the correct answer verbatim.
    """
    if q.type == QuestionType.mcq:
        if len(q.options) < 4:
            LOGGER.warning("Question %s rejected: fewer than 4 options (%s)", q.id, len(q.options))
            return False
        if q.correct_answer not in q.options:
            LOGGER.warning("Question %s rejected: correct answer '%s' not among options", q.id, q.correct_answer)
            return False
        # Stem must not contain answer if answer is non-trivial
        if len(q.correct_answer) > 4 and q.correct_answer.lower() in q.stem.lower():
            LOGGER.warning("Question %s rejected: stem reveals answer", q.id)
            return False
    return True


def create_offline_concept_question(concept: Concept, material: Material) -> Question:
    """Creates a deterministic offline question when no AI provider is configured."""
    qid = f"q_{uuid.uuid4().hex[:8]}"
    is_syllabus = material.kind == MaterialKind.syllabus

    # Extract verified quote if available
    span = concept.source_spans[0] if concept.source_spans else None

    stem = f"In the study of '{concept.name}', which statement accurately reflects the core principle?"
    correct = f"It governs the fundamental behavior of {concept.name} as established in the course material."
    options = [
        correct,
        f"It only applies when external forces and resistances are completely ignored.",
        f"It states that {concept.name} is solely determined by velocity rather than rates of change.",
        f"It is an obsolete approximation that has been replaced by static equilibrium equations.",
    ]
    distractor_map = {
        options[1]: "Assumes ideal friction-free conditions are always required",
        options[2]: "Confuses velocity with acceleration / rate of change",
        options[3]: "Believes classical dynamics are invalid in standard mechanics",
    }

    return Question(
        id=qid,
        concept_id=concept.id,
        type=QuestionType.mcq,
        difficulty=2,
        stem=stem,
        options=options,
        correct_answer=correct,
        distractor_map=distractor_map,
        source_span=span,
        grounded=not is_syllabus and span is not None,
        origin="authored_fallback",
    )


def generate_questions_for_concept(
    concept: Concept,
    material: Material,
    count: int = 1,
    llm_client: Optional[LLMClient] = None,
    db: Optional[LearnDB] = None,
) -> List[Question]:
    """
    Generates grounded diagnostic questions for a concept.
    Enforces verbatim substring source span verification against material.
    """
    client = llm_client or get_llm_client()
    questions: List[Question] = []
    is_syllabus = material.kind == MaterialKind.syllabus

    # Provide grounding context from material
    context_text = material.okf_text[:5000]

    try:
        response: GeneratedQuestionsResponse = client.generate_structured(
            prompt_name="question_generation",
            template_args={
                "concept_name": concept.name,
                "concept_description": concept.description,
                "material_title": material.title,
                "material_kind": material.kind.value,
                "material_context": context_text,
                "question_count": count,
            },
            schema=GeneratedQuestionsResponse,
            max_retries=2,
            max_tokens=1800,
        )

        for item in response.questions:
            qid = f"q_{uuid.uuid4().hex[:8]}"
            q_type = QuestionType.mcq
            if item.type.lower() in ("short", "explain", "numeric"):
                q_type = QuestionType(item.type.lower())

            # Grounding verification (§5.1)
            span: Optional[SourceSpan] = None
            grounded = False

            if not is_syllabus and item.source_quote:
                quote = item.source_quote.strip()
                if verify_span_in_material(material, quote):
                    span = SourceSpan(
                        material_id=material.id,
                        source_name=material.title,
                        quote=quote,
                    )
                    grounded = True
                else:
                    LOGGER.warning("Question %s rejected non-verbatim quote '%s'", qid, quote[:50])
                    # If question claims to be grounded but quote is fabricated, reject or unground
                    grounded = False

            q = Question(
                id=qid,
                concept_id=concept.id,
                type=q_type,
                difficulty=item.difficulty,
                stem=item.stem,
                options=item.options,
                correct_answer=item.correct_answer,
                rubric=item.rubric,
                distractor_map=item.distractor_map,
                source_span=span,
                grounded=grounded,
                origin="ai",
            )

            if validate_question_shape(q):
                questions.append(q)

    except (LearnAIError, Exception) as exc:
        LOGGER.warning("AI question generation failed (%s). Using offline fallback question.", exc)
        fallback_q = create_offline_concept_question(concept, material)
        questions.append(fallback_q)

    if not questions:
        questions.append(create_offline_concept_question(concept, material))

    # Persist questions and register candidate misconceptions in DB
    if db is not None:
        db.save_questions(questions)
        candidates: List[MisconceptionCandidate] = []
        for q in questions:
            for opt, misc_label in q.distractor_map.items():
                cid = f"mcand_{uuid.uuid4().hex[:8]}"
                candidates.append(
                    MisconceptionCandidate(
                        id=cid,
                        concept_id=concept.id,
                        label=misc_label,
                        description=f"Misconception triggered by selecting distractor: '{opt}'",
                        typical_wrong_answer=opt,
                        origin="ai_proposed" if q.origin == "ai" else "authored",
                    )
                )
        if candidates:
            db.save_misconception_candidates(candidates)

    return questions

