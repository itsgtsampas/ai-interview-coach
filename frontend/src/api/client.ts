import type {
  Answer, CoachResponse, CoverLetter, DocumentKind, DocumentOut, Evaluation,
  LetterTone, MatchReport, Progress, ProfileOut, ProfileUpdate, Question,
  Scorecard, SessionOut, Suggestion, User,
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

  getProfile: () => request<ProfileOut>("/profile"),
  updateProfile: (body: ProfileUpdate) =>
    request<ProfileOut>("/profile", { method: "PUT", body: JSON.stringify(body) }),
  uploadProfileCv: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<ProfileOut>("/profile/cv", { method: "POST", body: fd });
  },
  deleteProfileCv: () => request<ProfileOut>("/profile/cv", { method: "DELETE" }),

  listSessions: () => request<SessionOut[]>("/sessions"),
  getSession: (id: number) => request<SessionOut>(`/sessions/${id}`),
  createSession: (title: string, target_role: string, use_profile_cv = true) =>
    request<SessionOut>("/sessions", {
      method: "POST",
      body: JSON.stringify({ title, target_role, use_profile_cv }),
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
  pasteDocument: (id: number, kind: DocumentKind, text: string, title: string) =>
    request<DocumentOut>(`/sessions/${id}/documents/text?kind=${kind}`, {
      method: "POST",
      body: JSON.stringify({ text, title }),
    }),
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

  progress: () => request<Progress>("/progress"),

  suggestRewrite: (sessionId: number, itemId: number) =>
    request<Suggestion>(`/sessions/${sessionId}/match-items/${itemId}/rewrite`, {
      method: "POST",
    }),
  listRewrites: (sessionId: number) =>
    request<Suggestion[]>(`/sessions/${sessionId}/rewrites`),

  getCoverLetter: (id: number) => request<CoverLetter>(`/sessions/${id}/cover-letter`),
  writeCoverLetter: (id: number, tone: LetterTone) =>
    request<CoverLetter>(`/sessions/${id}/cover-letter`, {
      method: "POST",
      body: JSON.stringify({ tone }),
    }),

  /** Fetch the PDF as a blob.
   *
   *  It cannot be a plain link: the endpoint needs the Authorization header, and
   *  putting the token in a query string would leak it into history and logs.
   *  The caller is responsible for revoking the object URL. */
  scorecardPdf: async (id: number): Promise<{ url: string; filename: string }> => {
    const headers = new Headers();
    const t = token.get();
    if (t) headers.set("Authorization", `Bearer ${t}`);

    const res = await fetch(`/api/v1/sessions/${id}/scorecard.pdf`, { headers });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.error ?? "export_failed",
        body.message ?? "The export failed.", body.details ?? {});
    }
    const disposition = res.headers.get("content-disposition") ?? "";
    const match = /filename="([^"]+)"/.exec(disposition);
    return {
      url: URL.createObjectURL(await res.blob()),
      filename: match?.[1] ?? "scorecard.pdf",
    };
  },
};

export type { Evaluation };
