import type {
  Answer, CoachResponse, DocumentKind, DocumentOut, Evaluation,
  MatchReport, Question, Scorecard, SessionOut, User,
} from "./types";

const TOKEN_KEY = "cvcoach.token";

export const token = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (v: string) => localStorage.setItem(TOKEN_KEY, v),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

/** The backend's single error shape (see app/exceptions.py). */
export class ApiError extends Error {
  code: string;
  details: Record<string, unknown>;
  status: number;

  constructor(status: number, code: string, message: string, details = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const t = token.get();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`/api/v1${path}`, { ...init, headers });
  if (res.status === 204) return undefined as T;

  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401) token.clear();
    throw new ApiError(
      res.status,
      body.error ?? "request_failed",
      body.message ?? body.detail ?? "Something went wrong.",
      body.details ?? {},
    );
  }
  return body as T;
}

export const api = {
  register: (email: string, full_name: string, password: string) =>
    request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, full_name, password }),
    }),

  login: async (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password });
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new ApiError(res.status, body.error ?? "login_failed",
        body.message ?? "Incorrect email or password.");
    }
    token.set(body.access_token);
    return body.access_token as string;
  },

  me: () => request<User>("/auth/me"),

  listSessions: () => request<SessionOut[]>("/sessions"),
  getSession: (id: number) => request<SessionOut>(`/sessions/${id}`),
  createSession: (title: string, target_role: string) =>
    request<SessionOut>("/sessions", {
      method: "POST",
      body: JSON.stringify({ title, target_role }),
    }),
  deleteSession: (id: number) => request<void>(`/sessions/${id}`, { method: "DELETE" }),

  uploadDocument: (id: number, kind: DocumentKind, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<DocumentOut>(`/sessions/${id}/documents?kind=${kind}`, {
      method: "POST",
      body: fd,
    });
  },
  listDocuments: (id: number) => request<DocumentOut[]>(`/sessions/${id}/documents`),

  runAnalysis: (id: number) =>
    request<MatchReport>(`/sessions/${id}/analysis`, { method: "POST" }),
  getAnalysis: (id: number) => request<MatchReport>(`/sessions/${id}/analysis`),

  generateQuestions: (id: number, technical = 5, behavioural = 3) =>
    request<Question[]>(
      `/sessions/${id}/questions?technical=${technical}&behavioural=${behavioural}`,
      { method: "POST" },
    ),
  listQuestions: (id: number) => request<Question[]>(`/sessions/${id}/questions`),

  submitAnswer: (questionId: number, text: string, duration_seconds: number) =>
    request<Answer>(`/questions/${questionId}/answers`, {
      method: "POST",
      body: JSON.stringify({ text, duration_seconds }),
    }),
  getAnswer: (questionId: number) => request<Answer>(`/questions/${questionId}/answer`),

  buildScorecard: (id: number) =>
    request<Scorecard>(`/sessions/${id}/scorecard`, { method: "POST" }),
  getScorecard: (id: number) => request<Scorecard>(`/sessions/${id}/scorecard`),

  askCoach: (id: number, message: string) =>
    request<CoachResponse>(`/sessions/${id}/coach`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
};

export type { Evaluation };
