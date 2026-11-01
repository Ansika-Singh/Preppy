export type ErrorType =
  | 'knowledge_gap'
  | 'conceptual_misunderstanding'
  | 'calculation_error'
  | 'careless_mistake'
  | 'incomplete_reasoning'
  | 'uncertain';

export type MaterialKind = 'syllabus' | 'notes' | 'textbook';

export type QuestionType = 'mcq' | 'short' | 'numeric' | 'explain';

export type MisconceptionState = 'suspected' | 'uncertain' | 'confirmed' | 'resolved';

export type MasteryBand = 'insufficient_evidence' | 'weak' | 'moderate' | 'strong';

export interface SourceSpan {
  material_id: string;
  source_name: string;
  quote: string;
  page?: number | null;
}

export interface Material {
  id: string;
  student_id: string;
  title: string;
  kind: MaterialKind;
  source_ref?: string | null;
  content_hash: string;
  okf_text: string;
  created_at: number;
}

export interface Concept {
  id: string;
  material_id: string;
  parent_id?: string | null;
  name: string;
  description: string;
  order_idx: number;
  prerequisites: string[];
  source_spans: SourceSpan[];
}

export interface MisconceptionCandidate {
  id: string;
  concept_id: string;
  label: string;
  description: string;
  typical_wrong_answer: string;
  origin: string;
}

export interface Question {
  id: string;
  concept_id: string;
  type: QuestionType;
  difficulty: number;
  stem: string;
  options: string[];
  correct_answer: string;
  rubric?: string | null;
  distractor_map: Record<string, string>;
  source_span?: SourceSpan | null;
  grounded: boolean;
  origin: string;
  created_at?: number;
}

export interface Attempt {
  id: string;
  student_id: string;
  question_id: string;
  concept_id: string;
  answer_text: string;
  selected_option?: string | null;
  reasoning_text: string;
  confidence?: number | null;
  is_correct: boolean;
  score: number;
  time_ms: number;
  session_id: string;
  created_at: number;
}

export interface MisconceptionRecord {
  id: string;
  attempt_id: string;
  concept_id: string;
  error_type: ErrorType;
  misconception_id?: string | null;
  state: MisconceptionState;
  confidence: number;
  evidence_quote?: string | null;
  explanation: Record<string, any>;
  created_at: number;
  resolved_at?: number | null;
}

export interface Mastery {
  student_id: string;
  concept_id: string;
  mastery: number;
  attempts: number;
  correct: number;
  consecutive_correct: number;
  last_outcomes: number[];
  has_transfer_success: boolean;
  consistency: number;
  band: MasteryBand;
  updated_at: number;
}

export interface RevisionItem {
  student_id: string;
  concept_id: string;
  due_at: number;
  interval_days: number;
  ease: number;
  last_reviewed_at: number;
  reason_code: string;
  reason_text: string;
}

export interface LearnStatus {
  active_provider: string;
  provider_code: string;
  is_cloud: boolean;
  is_connected: boolean;
  call_budget_total: number;
  call_budget_used: number;
  call_budget_remaining: number;
  student_id: string;
  student_name: string;
}

export interface MisconceptionAnalysisResult {
  record_id: string;
  error_type: ErrorType;
  state: MisconceptionState;
  confidence: number;
  evidence_quote?: string | null;
  rationale: string;
  needs_probe: boolean;
  why_wrong: string;
  core_idea: string;
  analogy: string;
  escalation_style: string;
  exceeded_loop_cap: boolean;
  followup_question: Question;
  grounded_source?: string | null;
  source_label: string;
}

// -----------------------------------------------------------------------------
// Read -> Recall (Voice) Types (§5.2)
// -----------------------------------------------------------------------------
export interface ChunkKeyIdea {
  id: string;
  claim: string;
  supporting_quote: string;
}

export interface Chunk {
  id: string;
  material_id: string;
  concept_id?: string | null;
  idx: number;
  text: string;
  word_count: number;
  key_ideas: ChunkKeyIdea[];
  key_ideas_status: string;
}

export type RecallStatus = 'covered' | 'partially_covered' | 'missed' | 'contradicted';

export type ExtraClaimType = 'correct_extension' | 'neutral' | 'misconception' | 'irrelevant';

export interface ExtraClaim {
  claim: string;
  student_quote: string;
  type: ExtraClaimType;
}

export interface RecallKeyIdeaEvaluation {
  key_idea_id: string;
  claim: string;
  status: RecallStatus;
  student_quote?: string | null;
  notes_quote?: string | null;
  feedback: string;
}

export interface RecallAnalysisResult {
  chunk_id: string;
  coverage_score: number;
  raw_coverage_score: number;
  is_too_short: boolean;
  recitation_ratio: number;
  is_recited: boolean;
  peeked: boolean;
  evaluations: RecallKeyIdeaEvaluation[];
  extra_claims: ExtraClaim[];
  misconceptions_detected: string[];
  summary: string;
  linked_misconception_record_ids: string[];
}

export interface RecallSession {
  id: string;
  student_id: string;
  chunk_id: string;
  concept_id?: string | null;
  read_ms: number;
  peeked: boolean;
  input_method: string;
  transcript_raw: string;
  transcript_final: string;
  coverage: number;
  recitation_ratio: number;
  accuracy_flags: Record<string, any>;
  analysis: RecallAnalysisResult;
  created_at: number;
}

