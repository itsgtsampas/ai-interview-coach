# AI Interview Coach

Upload your CV and a job description. Get a **grounded gap analysis** — every verdict
linked to the exact sentence it was drawn from — then personalised interview questions,
rubric-based feedback on your answers, and a readiness scorecard.

Final project for **AI for Developers**, AUEB Centre for Training and Lifelong Learning
(instructor: Panagiotis Moschos).

---

## Documentation

**[docs/documentation.pdf](docs/documentation.pdf)** — the full write-up: purpose,
architecture and data flow, every GenAI technique and why it was chosen, the RAG
pipeline, the FastAPI endpoints, the UI, the evaluation results, a worked
example, limitations and future extensions. Screenshots are in
[docs/screenshots/](docs/screenshots/).

Supporting detail lives alongside it: [DESIGN.md](docs/DESIGN.md) for the design
rationale and the decisions taken along the way, [prompts.md](docs/prompts.md) for
all eight prompts with their PCTF blocks and a 1-5 rubric assessment of each,
[evaluation.md](docs/evaluation.md) for the harness and what it found, and
[IMPLEMENTATION.md](docs/IMPLEMENTATION.md) for seminar-technique coverage.

---

## Runs on the OpenAI API

Every reasoning stage — requirement extraction, the gap analysis, question generation,
answer scoring, the scorecard, the coach agent, bullet rewrites and the cover letter —
is a real call to `gpt-4o-mini` through `https://api.openai.com/v1/chat/completions`.
See [Switching on a real model](#switching-on-a-real-model) for setup, and
[`docs/prompts.md`](docs/prompts.md) for the prompt behind each stage.

Nothing in the application is hardwired to OpenAI. Providers implement a single
`LLMProvider` protocol and are selected by one setting, so swapping models — or vendors —
moves no calling code. `app/llm/structured.py` is the only thing that reaches a provider
at all: it validates every response against a Pydantic contract, retries once on a schema
failure, enforces the spend ceiling, and writes a telemetry row either way.

### The test double

`app/llm/stub.py` implements the same protocol without a network call, and exists for two
jobs: it keeps the **89-test suite** free, instant and deterministic, and it lets the
**eval harness** measure retrieval and chunking changes with the model held still.

It is a test double, not a way to run the product — selecting it logs a warning, and the
application defaults to `openai`. It is worth knowing that it is not a mock returning
canned text: it derives each stage from the actual documents using rule-based IDF-weighted
analysis, which is what makes the retrieval ablations meaningful.

One test run makes **86 model calls**. Against the API that is ~$0.05 and several minutes
of non-deterministic network; against the double it is free and takes 30 seconds.

---

## Quick start

**Requirements:** Python 3.11+ and Node 18+. Nothing else, and no accounts.

### 1. Backend

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/make_fixtures.py    # sample CV + job description PDFs
.venv/bin/python scripts/demo_seed.py        # optional: a fully worked demo session
.venv/bin/python -m uvicorn app.main:app --port 8000 --reload
```

API docs (Swagger) at <http://127.0.0.1:8000/docs>.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. If you ran the seed script, sign in as
**demo@example.com / demo1234**; otherwise create an account on the sign-in screen.

### With Docker

```bash
docker compose up
```

---

## What it does

| Stage | What happens | GenAI technique |
|---|---|---|
| **1. Gap analysis** | Extracts every requirement from the job description, retrieves CV evidence for each, and judges it — with a verbatim quote and page number, or an honest "no evidence". | Zero-shot extraction, RAG, chain-of-thought, enforced citations |
| **2. Questions** | Writes technical and behavioural questions from those gaps, riskiest first, each anchored in your own words. | Few-shot (3 exemplars), prompt chaining |
| **3. Feedback** | Scores your answer 1–5 on five rubric dimensions — STAR for behavioural, a technical rubric otherwise — reasoning *before* scoring, then gives a model answer and the follow-up a real interviewer would ask. | Few-shot calibration anchors, chain-of-thought, structured outputs |
| **4. Scorecard** | Combines CV match (40%) with answer quality (60%) into a readiness score, competency averages, and prioritised action items. | Prompt chaining over stored stage outputs |
| **5. Cover letter** | Writes a letter from the requirements your CV *evidenced*, and the sentences that evidenced them. Requirements it could not find are never passed to the model, so they cannot appear as strengths. Streams as it is written. | Prompt chaining, structural grounding, SSE |
| **6. Coach** | Answers free-form questions by choosing between four tools, and shows every lookup it made. | ReAct agent, tool calling |

Alongside the stage sequence:

| | |
|---|---|
| **CV bullet rewrites** | For any unmet requirement, the shape of the bullet that would answer it — with every fact you must supply left as a `[placeholder]`. It writes a template, never a claim: a model asked to "fix the gap" will happily invent *"Led migration of 40 microservices to Kubernetes"* for someone who has never touched it. |
| **Progress** | Across every application at once. This is the only place a *recurring* gap becomes visible — missing one posting's requirement is a mismatch, missing the same one in four is the thing to go and learn. |
| **PDF export** | The scorecard laid out for print, with the evidence quotes and the prompt versions that produced the numbers. |

---

## Switching on a real model

The application calls the OpenAI API, so it needs a key before it will start
doing useful work:

1. Get a key at `platform.openai.com` and put it in `backend/.env` (copy
   `.env.example` first). `.env` is gitignored — never commit it, and never
   paste a key into a chat or an issue.
2. Add credit to the account. The API is **prepaid** and separate from any
   ChatGPT subscription; a key with no credit authenticates and then refuses
   every call with `insufficient_quota`.
3. Verify it before running anything else:

```bash
cd backend && .venv/bin/python -m evals.preflight
```

That makes one small real call — roughly a tenth of a cent — through the whole
chain: settings, provider, HTTP, JSON mode, Pydantic validation, telemetry. If
it fails, nothing else will work either, and it names the usual causes.

**Spend is capped.** `MAX_SPEND_USD` (default `$5.00`) is a hard ceiling on
cumulative cost across the database. Every call checks the running total before
reaching a provider, so a retry loop or a runaway eval sweep cannot exceed it.
Both model tiers default to `gpt-4o-mini`; `gpt-4o` is about 17x the price and
has to be opted into explicitly.

`EMBEDDING_PROVIDER` is separate and stays `stub` unless you change it: retrieval
currently uses a hashing vectoriser, not semantic embeddings. Switching it alters
retrieval *and* requires re-indexing every document, so it is worth doing as its
own measured step rather than confounding two variables at once.

**No key?** The app will not run without one. The test suite and eval harness
still will — both pin the test double explicitly — so `pytest` and
`python -m evals.run` work on a fresh clone with no account at all.

---

## Running the tests

```bash
cd backend
.venv/bin/python -m pytest -q
```

78 tests, fully offline and deterministic — including an end-to-end run of every stage, a
check that **no citation appears that is not verbatim in the source CV**, a check that
**no digit in a CV suggestion falls outside a placeholder**, and a check that the rate
limiter charges two accounts behind one address separately.

---

## Project layout

```
backend/
  app/
    main.py config.py db.py security.py dependencies.py exceptions.py middleware.py
    models/     SQLModel tables (users, sessions, documents, reports, answers, llm_call)
    schemas/    Pydantic request/response DTOs
    routers/    auth · sessions · documents · analysis · interview · health
    services/   ingestion · analysis · questions · evaluation · scorecard
    rag/        loader · chunker · embedder · store · query_analysis · fusion · rerank · retriever
    llm/        base · contracts · stub · openai_provider · structured · cache · tokens
    prompts/    PCTF templates, one per stage, each versioned
    agents/     coach agent + tools
  tests/    evals/data/    scripts/
frontend/
  src/  api/ · lib/ · components/ · pages/ · styles.css
docs/
  DESIGN.md            architecture and rationale
  IMPLEMENTATION.md    what is built, what is pending
```

---

## Security and privacy notes

- Passwords are bcrypt-hashed; access is JWT bearer, expiring.
- Uploads are validated by magic bytes as well as extension, size- and page-capped, and
  stored outside any served path under a per-user directory.
- **Every vector query is filtered by `user_id` and `session_id`**, so one user's CV can
  never enter another user's model context.
- A CV is personal data: `DELETE /sessions/{id}` erases the database rows, the Chroma
  vectors and the PDF files.
- Untrusted document text is delimiter-fenced with an explicit data-not-instruction
  notice, and a strict output schema is the second line of defence.
- `.env` is git-ignored; `.env.example` documents every variable.

## Known limitations

- Scanned/image PDFs are rejected with a clear message rather than silently misread. OCR
  is out of scope.
- Retrieval is still lexical, not semantic: `EMBEDDING_PROVIDER` defaults to a hashing
  vectoriser, so a paraphrase sharing no vocabulary with the requirement can be missed.
  The reasoning stages are unaffected — those are real model calls. Setting
  `EMBEDDING_PROVIDER=openai` and re-indexing fixes it.
- `create_all` builds the schema, with a helper that adds missing nullable columns on
  startup; a production deployment would use Alembic migrations.
- Greek and English are supported end to end: documents, model output, interface and the
  PDF export. A third language would need its own stopword list and a look at the
  stemmer — the tokenizer and the folding are already script-agnostic.
- Offline, the stub answers in about five milliseconds, so an SSE stream finishes before
  the browser paints and the streaming UI is not visible. Set `STUB_STREAM_DELAY_MS=18` to
  demonstrate the transport without an API key — it is a demo aid and defaults to `0`,
  because it adds latency that does not exist.
