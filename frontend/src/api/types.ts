/** Mirrors the FastAPI response models. The backend serves an OpenAPI schema at
 *  /openapi.json, so these can be regenerated with openapi-typescript. */

export type DocumentKind = "cv" | "jd";
export type IngestStatus = "pending" | "processing" | "ready" | "failed";
export type EvidenceStatus = "strong" | "partial" | "missing";
export type RequirementCategory = "must_have" | "nice_to_have";
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
