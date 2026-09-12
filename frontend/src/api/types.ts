/** Mirrors the FastAPI response models. The backend serves an OpenAPI schema at
 *  /openapi.json, so these can be regenerated with openapi-typescript. */

export type DocumentKind = "cv" | "jd";
export type DocumentSource = "pdf" | "text";
export type IngestStatus = "pending" | "processing" | "ready" | "failed";
export type EvidenceStatus = "strong" | "partial" | "missing";
export type RequirementCategory = "must_have" | "nice_to_have";
export type RequirementKind = "evidenceable" | "behavioural";
export type QuestionCategory = "technical" | "behavioural";
export type SessionStatus =
  | "created" | "ingesting" | "ready" | "analysed" | "in_progress" | "completed";

export interface User {
  id: number;
  email: string;
  full_name: string;
  created_at: string;
}

export interface DocumentOut {
  id: number;
  kind: DocumentKind;
  source: DocumentSource;
  original_filename: string;
  ingest_status: IngestStatus;
  ingest_error: string | null;
  page_count: number;
  char_count: number;
  chunk_count: number;
}

export interface SessionOut {
  id: number;
  title: string;
  target_role: string;
  status: SessionStatus;
  created_at: string;
  documents: DocumentOut[];
  has_analysis: boolean;
  question_count: number;
  answered_count: number;
  readiness_score: number | null;
}

export interface MatchItem {
  id: number;
  requirement: string;
  category: RequirementCategory;
  kind: RequirementKind;
  status: EvidenceStatus;
  confidence: number;
  reasoning: string;
  evidence_quote: string | null;
  evidence_page: number | null;
  evidence_section: string | null;
}

export interface MatchReport {
  id: number;
  session_id: number;
  overall_score: number;
  verdict: string;
  summary: string;
  prompt_version: string;
  items: MatchItem[];
  counts: Record<string, number>;
}

export interface Question {
  id: number;
  category: QuestionCategory;
  text: string;
  rationale: string;
  difficulty: number;
  linked_requirement: string;
  order_index: number;
  answered: boolean;
}

export interface Criterion {
  name: string;
  score: number;
}

export interface Evaluation {
  id: number;
  answer_id: number;
  rubric: "star" | "technical";
  overall_score: number;
  reasoning: string;
  criteria: Criterion[];
  strengths: string[];
  improvements: string[];
  model_answer: string;
  follow_up_question: string;
  prompt_version: string;
}

export interface Answer {
  id: number;
  question_id: number;
  text: string;
  duration_seconds: number;
  evaluation: Evaluation | null;
}

export interface ActionItem {
  priority: "high" | "medium" | "low";
  title: string;
  why: string;
  how: string;
}

export interface Scorecard {
  id: number;
  session_id: number;
  readiness_score: number;
  readiness_band: string;
  summary: string;
  competencies: Record<string, number>;
  strengths: string[];
  gaps: string[];
  action_items: ActionItem[];
}

export interface CoachStep {
  thought: string;
  tool: string | null;
  observation: string | null;
}

export interface CoachResponse {
  answer: string;
  steps: CoachStep[];
}

export type Seniority = "intern" | "junior" | "mid" | "senior" | "lead" | "principal";

export interface ProfileUpdate {
  headline: string;
  seniority: Seniority | null;
  years_experience: number | null;
  target_roles: string;
  location: string;
  languages: string;
  summary: string;
  linkedin_url: string;
  github_url: string;
  portfolio_url: string;
  phone: string;
  /** Europass fields. Stored, shown back, and never sent to a model. */
  date_of_birth: string | null;
  gender: string;
  nationality: string;
}

export interface ProfileOut extends ProfileUpdate {
  id: number;
  full_name: string;
  email: string;
  age: number | null;
  has_cv: boolean;
  cv_filename: string;
  cv_page_count: number;
  cv_uploaded_at: string | null;
  updated_at: string;
}

/* --- cross-session progress ---------------------------------------------- */

export interface ProgressPoint {
  session_id: number;
  title: string;
  target_role: string;
  created_at: string;
  match_score: number | null;
  readiness_score: number | null;
  answers: number;
  mean_answer_score: number | null;
}

export interface RecurringGap {
  requirement: string;
  missing_in: number;
  sessions: string[];
}

export interface CompetencyTrend {
  name: string;
  first: number;
  latest: number;
  delta: number;
  points: number[];
}

export interface Progress {
  sessions_total: number;
  sessions_scored: number;
  answers_total: number;
  mean_answer_score: number | null;
  best_readiness: number | null;
  latest_readiness: number | null;
  readiness_delta: number | null;
  mean_match: number | null;
  /** False when there are too few scored sessions for a line to mean anything. */
  has_trend: boolean;
  points: ProgressPoint[];
  recurring_gaps: RecurringGap[];
  competencies: CompetencyTrend[];
}

/* --- derived writing ------------------------------------------------------ */

export interface Suggestion {
  id: number;
  match_item_id: number;
  requirement: string;
  bullet: string;
  premise: string;
  why: string;
  if_you_cannot: string;
  /** The facts the candidate must supply. Never filled in by the model. */
  placeholders: string[];
  prompt_version: string;
}

export type LetterTone = "plain" | "warm" | "formal";

export interface CoverLetter {
  id: number;
  session_id: number;
  tone: LetterTone;
  subject: string;
  body: string;
  claims_used: string[];
  prompt_version: string;
  created_at: string;
}
