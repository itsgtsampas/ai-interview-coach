# Implementation status — seminar technique coverage

Build date: 2026-09-07. Backend and frontend both run; 18 tests pass offline.

Legend: **✅ built and exercised** · **🟡 partial** · **⬜ not started**

---

## 1. Prompt engineering

| Technique | Deck | Status | Where | Note |
|---|---|---|---|---|
| Zero-shot | Άσκηση 1 | ✅ | `prompts/extract_requirements.py` | Requirement extraction; also the eval baseline. |
| Few-shot | Άσκηση 2 | ✅ | `prompts/generate_questions.py` (3 exemplars), `prompts/evaluate_answer.py` (2 calibration anchors at the 2 and 4 marks) | Anchors exist specifically to stop score inflation. |
| Chain-of-Thought | Άσκηση 3, 2.3 | ✅ | `prompts/evaluate_answer.py`, `prompts/analyse_match.py` | Reasoning is produced *before* scores, stored in `evaluation.reasoning`, and shown in the UI under "Why this score". |
| PCTF | 2.2, Άσκηση 4 | ✅ | `prompts/blocks.py` — all 6 prompts | Every prompt is four labelled blocks. |
| Delimiters | 2.3 | ✅ | `prompts/blocks.py` | XML fencing + explicit data-not-instruction notice on all untrusted text. |
| ReAct | 2.3 | ✅ | `agents/coach.py` | Bounded 4-iteration loop; full trace returned and rendered. |
| Structured outputs | Assignment p.6 | ✅ | `llm/contracts.py`, `llm/structured.py` | Pydantic validation + one repair retry + `502` on second failure. |
| Tool calling | Assignment p.8 | ✅ | `agents/tools.py` | 4 JSON-schema tools, each user/session-scoped. |
| Prompt chaining | Proposal | ✅ | `services/` stages 1→4 | Each stage consumes the previous stage's stored output. |
| Prompt versioning | — | ✅ | `prompts/registry.py`, `llm_call.prompt_version` | Any stored output traces to the prompt that made it. |

## 2. RAG

| Technique | Deck | Status | Where |
|---|---|---|---|
| LLM knowledge limits → RAG rationale | 5.1 | ✅ | Documented in `DESIGN.md` §2.1 |
| 8-stage pipeline (index + query) | 5.2 | ✅ | `rag/` |
| Document loading (PDF) | 5.2 | ✅ | `rag/loader.py` |
| Scan detection guard | — | ✅ | `rag/loader.py` — `422` with an actionable message |
| Section-aware splitting | 5.4 | ✅ | `rag/chunker.py` |
| Parent–child chunking (small-to-big) | 5.4 | ✅ | `rag/chunker.py` + `retriever.py` |
| Contextual chunking (breadcrumb prefix) | 5.4 | ✅ | `rag/chunker.py` |
| Recursive/fixed fallback splitting | 5.4 | ✅ | `rag/chunker.py` when headings are undetectable |
| Embeddings | 5.3 | ✅ | `rag/embedder.py` — pluggable; stub hashing vectoriser + OpenAI `text-embedding-3-small` |
| Vector DB (ChromaDB) | 5.3 | ✅ | `rag/store.py`, persistent, cosine |
| Metadata filtering / RBAC isolation | 5.4 | ✅ | Every query filters `user_id` + `session_id` |
| Multi-query expansion | 5.4 | ✅ | `rag/query_analysis.py` (+ domain synonym lexicon) |
| Hybrid search (BM25 + dense) | 5.3 | ✅ | `rag/retriever.py` via `rank_bm25` |
| Reciprocal Rank Fusion | 5.4 | ✅ | `rag/fusion.py` |
| Re-ranking | 5.4 | ✅ | `rag/rerank.py` — behind an interface, with a no-op ablation baseline |
| Citations & grounding | 5.2 | ✅ | Enforced in the prompt, verified in code (`services/analysis.verify_citation`), tested |
| Relevance floor | 5.3 | ✅ | `retriever.SCORE_FLOOR` |
| Caching | 5.4 | ✅ | `llm/cache.py` — embeddings + deterministic completions |
| Cost / token accounting | 5.4 | ✅ | `llm_call` table |
| Fallback strategies | 5.4 | ✅ | Repair retry, provider errors → `502`/`503`, degraded `/health/ready` |
| **HyDE** | 5.4 | ⬜ | Not implemented |
| **Step-back prompting** | 5.4 | ⬜ | Not implemented |
| **Semantic chunking** (embedding-boundary) | 5.4 | ⬜ | We do section + parent-child + contextual instead |
| **Self-query retriever** | 5.4 | ⬜ | Not implemented |
| **Semantic (fuzzy) cache** | 5.4 | 🟡 | Exact content-hash cache only |

## 3. Evaluation — **built**

`evals/` — run with `python -m evals.run`. Results in [evaluation.md](evaluation.md).

| Technique | Deck | Status | Note |
|---|---|---|---|
| Golden dataset | 5.4 | ✅ | 3 CV×JD pairs, 31 labelled requirements, 13 retrieval probes, 12 hand-scored answers, 10 ordering judgements. Synthetic, committed. |
| Retrieval metrics (hit@k, MRR, mean rank) | 5.4 | ✅ | `evals/metrics.py`. hit@1 0.769, MRR 0.885. |
| Citation validity | — | ✅ | 1.000 — no hallucinated citation in any configuration. |
| Context-precision analogue (`citation_in_context`) | 5.4 | ✅ | 1.000 |
| Faithfulness analogue (`summary_numeric_consistency`) | 5.4 | ✅ | 1.000 — prose counts must match structured verdicts. |
| Status accuracy vs human labels | — | ✅ | 0.839 exact, 0.935 within one. |
| False / missed evidence rates | — | ✅ | The two directions of error, tracked separately. |
| Answer-score agreement (MAE, bias, Spearman, pairwise) | 5.4 | ✅ | Spearman 0.867, pairwise 0.900, bias −0.667. |
| LLM-as-judge | 5.4 | ✅ | `evals/judges.py`, pluggable. Heuristic judge offline; `--judge llm` with a real provider. |
| Ablation tables | 5.4 | ✅ | 6 configurations across chunking and retrieval. |
| Self-consistency | 5.4 | ✅ | Implemented, clears the cache between repeats. Reads 0.000 because the stub is deterministic — informative only with a real provider. |
| Metric unit tests | — | ✅ | `tests/test_metrics.py`, 17 tests. |
| **Prompt evaluation of our own prompts** (1–5 rubric) | Άσκηση 5 | ⬜ | `docs/prompts.md` still to write. |
| **Few-shot vs zero-shot prompt ablation** | Άσκηση 2 | ⬜ | Needs a real provider: the stub ignores prompt wording. |

## 4. FastAPI / backend

| Deck section | Status | Where |
|---|---|---|
| 01 Type hints, ASGI, auto-docs | ✅ | throughout; `/docs`, `/redoc` |
| 02 Path/Query params, `Annotated`, `Enum`, constraints | ✅ | routers |
| 03 Pydantic models, nested, `Field`, `@field_validator` | ✅ | `schemas/`, `schemas/auth.py` password validator |
| 04 `response_model`, status codes (201/202/204) | ✅ | routers |
| 05 `HTTPException` + custom handlers + validation override | ✅ | `exceptions.py` — one JSON error shape everywhere |
| 06 Dependency injection, `yield` teardown, sub-dependencies | ✅ | `dependencies.py` |
| 07 async vs sync, `BackgroundTasks` | ✅ | Ingestion runs in background; upload returns `202` |
| 08 SQLModel + SQLite, CRUD, relationships | ✅ | `models/`, `db.py` |
| 09 OAuth2 password flow, JWT, bcrypt, `get_current_user` | ✅ | `security.py`, `routers/auth.py` |
| 10 `APIRouter`, project structure, `pydantic-settings` + `.env` | ✅ | `routers/`, `config.py` |
| 11 CORS, custom middleware, lifespan | ✅ | `main.py`, `middleware.py` (request-id + timing) |
| 12 pytest, `TestClient`, `dependency_overrides`, in-memory DB | ✅ | `tests/` — 78 passing |
| 13 File uploads (`UploadFile`) | ✅ | `routers/documents.py` |
| 13 WebSockets | ⬜ | **Deliberately omitted** — nothing here is bidirectional. SSE was built instead: ordinary HTTP, so it inherits the existing auth, CORS and proxy config. See DESIGN §16.2. |
| Server-Sent Events (`StreamingResponse`) | ✅ | `sse.py`, `routers/coaching.py`, `routers/interview.py` — real token streaming for prose, stage events for structured output |
| Rate limiting (slowapi), keyed per account | ✅ | `ratelimit.py` — 429 in the app's own error shape, with `Retry-After` |
| Binary responses (PDF) with `Content-Disposition` | ✅ | `routers/export.py`, `services/pdf_export.py` |
| 14 Docker, production checklist, `/health` | ✅ | `Dockerfile`, `docker-compose.yml`, `/health/ready` |
| uv / `pyproject.toml` | 🟡 | `pyproject.toml` present; built with venv+pip because `uv` is not installed on this machine. `uv sync` will work as-is. |
| Alembic migrations | ⬜ | `create_all` for now; noted as a limitation. |

## 5. Frontend

| Item | Status |
|---|---|
| React 19 + Vite + TypeScript | ✅ |
| Sign in / register | ✅ |
| Dashboard | ✅ |
| Upload with background-ingest polling | ✅ |
| Gap analysis with evidence lines | ✅ |
| Practice room + timer + feedback | ✅ |
| Scorecard | ✅ |
| Coach with tool trace | ✅ |
| Responsive to mobile, keyboard focus, reduced-motion | ✅ |
| SSE streaming (cover letter tokens, evaluation stages) | ✅ `lib/sse.ts` — fetch-based, so the bearer token stays out of the query string |
| PDF export of the scorecard | ✅ `components/DownloadPdf.tsx` — authenticated blob fetch |
| CV bullet rewrites per gap | ✅ `components/RewriteCard.tsx` — placeholders rendered as unfinished |
| Cover letter with tone control | ✅ `pages/Letter.tsx` |
| Cross-session progress with charts | ✅ `pages/Progress.tsx`, `components/charts.tsx` — hand-rolled SVG |
| WCAG AA contrast on every text node | ✅ Audited at rendered size across all 7 pages; two palette tokens darkened (DESIGN §16.8) |
| Types generated from OpenAPI (`openapi-typescript`) | 🟡 Hand-written to mirror the schema |

## 6. Not started (project deliverables)

- `documentation.pdf` (the assessed written deliverable)
- `docs/prompts.md` — every prompt in PCTF form with version history, scored on the
  Άσκηση 5 rubric. Now covers **eight** stages: the original five plus `coach_agent`,
  `rewrite_bullet` and `cover_letter`.
- Screenshots and demo video
- Running the three measurements the harness implements but could not exercise offline:
  the few-shot/zero-shot prompt ablation, self-consistency, and LLM-as-judge agreement.
  The provider is now live, so these are unblocked.

---

## Defects the eval harness found and fixed

Building `evals/` was not a formality — it surfaced four real defects that 18 passing tests
and good-looking demo output had both missed. Full detail in [evaluation.md](evaluation.md) §4.

1. Thresholds hand-tuned on one CV/JD pair did not generalise → re-swept on the full
   golden set. Status accuracy **0.710 → 0.806**.
2. The retrieval relevance floor discarded genuinely relevant passages on cross-domain
   pairs.
3. Evidence selection ignored the decisive-term gate, so a CV reading *"Built the customer
   dashboard in React and TypeScript"* was reported as **no evidence of React**. Status
   accuracy **0.806 → 0.839**, missed-evidence **0.167 → 0.000**.
4. Sentence splitting on `"."` broke `Next.js` into two tokens.

It also **talked me out of a change I would otherwise have shipped**: extending the
decisive-term gate halves invented evidence but causes a quarter of genuinely evidenced
requirements to be reported missing. Measured, rejected, recorded.

---

## Recommended next step

Write `docs/prompts.md` and the assessed `documentation.pdf`. The engineering is done and
measured; what remains is the written deliverable, which now has real numbers to cite.
