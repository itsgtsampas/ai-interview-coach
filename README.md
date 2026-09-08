# AI Interview Coach

Upload your CV and a job description. Get a **grounded gap analysis** — every verdict
linked to the exact sentence it was drawn from — then personalised interview questions,
rubric-based feedback on your answers, and a readiness scorecard.

Final project for **AI for Developers**, AUEB Centre for Training and Lifelong Learning
(instructor: Panagiotis Moschos).

---

## Runs with no API key

The application ships with a **deterministic local provider** (`LLM_PROVIDER=stub`) that
needs no OpenAI key, no network and no model download. It is not a mock returning canned
text: every stage derives its output from the actual CV and job description you upload,
using rule-based IDF-weighted analysis, and every citation is a real verbatim slice of a
retrieved chunk.

Switching to a real model is a two-line configuration change — no calling code moves:

```bash
LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

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
| **5. Coach** | Answers free-form questions by choosing between four tools, and shows every lookup it made. | ReAct agent, tool calling |

---

## Running the tests

```bash
cd backend
.venv/bin/python -m pytest -q
```

18 tests, fully offline and deterministic — including an end-to-end run of all five
stages and a check that **no citation appears that is not verbatim in the source CV**.

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
- The stub provider is lexical, not semantic: it matches vocabulary and known synonyms,
  so it will miss a paraphrase that shares no words. Switching to a real model and real
  embeddings removes this.
- `create_all` builds the schema; a production deployment would use Alembic migrations.
