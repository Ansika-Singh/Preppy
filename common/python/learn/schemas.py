from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ErrorType(str, Enum):
    knowledge_gap = "knowledge_gap"
    conceptual_misunderstanding = "conceptual_misunderstanding"
    calculation_error = "calculation_error"
    careless_mistake = "careless_mistake"
    incomplete_reasoning = "incomplete_reasoning"
    uncertain = "uncertain"


class MaterialKind(str, Enum):
    syllabus = "syllabus"
    notes = "notes"
    textbook = "textbook"


class QuestionType(str, Enum):
    mcq = "mcq"
    short = "short"
    numeric = "numeric"
    explain = "explain"


class MisconceptionState(str, Enum):
    suspected = "suspected"
    uncertain = "uncertain"
    confirmed = "confirmed"
    resolved = "resolved"


class MasteryBand(str, Enum):
    insufficient_evidence = "insufficient_evidence"
    weak = "weak"
    moderate = "moderate"
    strong = "strong"


class SourceSpan(BaseModel):
    material_id: str
    source_name: str
    quote: str
    page: Optional[int] = None

    @field_validator("quote")
    @classmethod
    def cap_quote_length(cls, v: str) -> str:
        # Enforce max 300 chars per prompt rules
        return v[:300].strip()


class Material(BaseModel):
    id: str
    student_id: str = "local"
    title: str
    kind: MaterialKind
    source_ref: Optional[str] = None
    content_hash: str
    okf_text: str
    created_at: int = 0


class Concept(BaseModel):
    id: str
    material_id: str
    parent_id: Optional[str] = None
    name: str
    description: str = ""
    order_idx: int = 0
    prerequisites: List[str] = Field(default_factory=list)
    source_spans: List[SourceSpan] = Field(default_factory=list)


class MisconceptionCandidate(BaseModel):
    id: str
    concept_id: str
    label: str
    description: str
    typical_wrong_answer: str
    origin: str = "ai_proposed"  # "ai_proposed" | "authored" | "student_observed"


class Question(BaseModel):
    id: str
    concept_id: str
    type: QuestionType = QuestionType.mcq
    difficulty: int = 2
    stem: str
    options: List[str] = Field(default_factory=list)
    correct_answer: str
    rubric: Optional[str] = None
    distractor_map: Dict[str, str] = Field(default_factory=dict)
    source_span: Optional[SourceSpan] = None
    grounded: bool = False
    origin: str = "ai"  # "ai" | "authored" | "sample"
    created_at: int = 0

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: int) -> int:
        return max(1, min(3, v))


class Attempt(BaseModel):
    id: str
    student_id: str = "local"
    question_id: Optional[str] = None
    chunk_id: Optional[str] = None
    concept_id: str
    source: str = "quiz"  # "quiz" | "recall"
    answer_text: str
    selected_option: Optional[str] = None
    reasoning_text: str = ""
    confidence: Optional[int] = None  # 1-3
    is_correct: bool = False
    score: float = 0.0  # 0.0 to 1.0
    time_ms: int = 0
    session_id: str = "default"
    created_at: int = 0

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            return max(1, min(3, v))
        return v


class MisconceptionRecord(BaseModel):
    id: str
    attempt_id: str
    concept_id: str
    error_type: ErrorType
    misconception_id: Optional[str] = None
    state: MisconceptionState = MisconceptionState.suspected
    confidence: float = 0.0
    evidence_quote: Optional[str] = None
    explanation: Dict[str, Any] = Field(default_factory=dict)
    created_at: int = 0
    resolved_at: Optional[int] = None


class MisconceptionAnalysis(BaseModel):
    """Pydantic schema for structured misconception classification (§6.2)."""
    error_type: ErrorType
    misconception_id: Optional[str] = None
    new_misconception_label: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_quote: Optional[str] = None
    rationale: str = Field(max_length=500)
    needs_probe: bool = False


class Remediation(BaseModel):
    """Pydantic schema for targeted remediation (§6.3)."""
    why_wrong: str
    core_idea: str
    analogy: str
    followup_question: Question
    grounded_in_span: Optional[SourceSpan] = None


class Mastery(BaseModel):
    student_id: str = "local"
    concept_id: str
    mastery: float = 0.50
    attempts: int = 0
    correct: int = 0
    consecutive_correct: int = 0
    last_outcomes: List[float] = Field(default_factory=list)
    has_transfer_success: bool = False
    consistency: float = 1.0
    band: MasteryBand = MasteryBand.insufficient_evidence
    updated_at: int = 0


class RevisionItem(BaseModel):
    student_id: str = "local"
    concept_id: str
    due_at: int
    interval_days: int = 1
    ease: float = 2.30
    last_reviewed_at: int = 0
    reason_code: str = "INITIAL"
    reason_text: str = ""


class LearnStatus(BaseModel):
    active_provider: str
    is_cloud: bool
    is_connected: bool
    call_budget_total: int
    call_budget_used: int
    call_budget_remaining: int
    student_id: str = "local"
    student_name: str = "Student"


# -----------------------------------------------------------------------------
# Read -> Recall (Voice) Schemas (§5.2)
# -----------------------------------------------------------------------------

class ChunkKeyIdea(BaseModel):
    id: str
    claim: str
    supporting_quote: str


class Chunk(BaseModel):
    id: str
    material_id: str
    concept_id: Optional[str] = None
    idx: int
    text: str
    word_count: int
    key_ideas: List[ChunkKeyIdea] = Field(default_factory=list)
    key_ideas_status: str = "ready"  # "pending" | "ready" | "failed"


class RecallStatus(str, Enum):
    covered = "covered"
    partially_covered = "partially_covered"
    missed = "missed"
    contradicted = "contradicted"


class ExtraClaimType(str, Enum):
    correct_extension = "correct_extension"
    neutral = "neutral"
    misconception = "misconception"
    irrelevant = "irrelevant"


class ExtraClaim(BaseModel):
    claim: str
    student_quote: str
    type: ExtraClaimType


class RecallKeyIdeaEvaluation(BaseModel):
    key_idea_id: str
    claim: str
    status: RecallStatus
    student_quote: Optional[str] = None
    notes_quote: Optional[str] = None
    feedback: str = ""


class RecallAnalysisResult(BaseModel):
    chunk_id: str
    coverage_score: float
    raw_coverage_score: float
    is_too_short: bool = False
    recitation_ratio: float = 0.0
    is_recited: bool = False
    peeked: bool = False
    evaluations: List[RecallKeyIdeaEvaluation] = Field(default_factory=list)
    extra_claims: List[ExtraClaim] = Field(default_factory=list)
    misconceptions_detected: List[str] = Field(default_factory=list)
    summary: str = ""
    linked_misconception_record_ids: List[str] = Field(default_factory=list)


class RecallSession(BaseModel):
    id: str
    student_id: str = "local"
    chunk_id: str
    concept_id: Optional[str] = None
    read_ms: int = 0
    peeked: bool = False
    input_method: str = "wispr_flow_dictation"  # "wispr_flow_dictation" | "browser_speech" | "typed"
    transcript_raw: str
    transcript_final: str
    coverage: float = 0.0
    recitation_ratio: float = 0.0
    accuracy_flags: Dict[str, Any] = Field(default_factory=dict)
    analysis: RecallAnalysisResult
    created_at: int = 0


