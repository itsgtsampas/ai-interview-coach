"""End-to-end: upload -> analyse -> question -> answer -> score -> coach.

Runs entirely offline against the stub provider, so it is deterministic and free.
"""

import pytest

STRONG_ANSWER = (
    "At Nexora I owned the checkout service. The problem was that p99 latency had "
    "reached 840ms and we were timing out during peak hours, which was costing us "
    "orders. I was responsible for the whole service, so I profiled it and found "
    "that we were opening a new database connection per request. I introduced "
    "connection pooling and migrated the hot path to async I/O in FastAPI. "
    "I chose pooling over adding read replicas because the bottleneck was "
    "connection setup, not read capacity, and replicas would have added "
    "replication lag we did not want on the checkout path. As a result p99 dropped "
    "from 840ms to 210ms over three weeks, measured on the same dashboard, and "
    "checkout timeouts fell by 90 percent. The pooling configuration is still in "
    "place today."
)

WEAK_ANSWER = "We improved the performance quite a lot and everyone was happy with the outcome."


@pytest.fixture
def ready_session(auth_client, cv_bytes, jd_bytes):
    """A session with both documents uploaded and indexed."""
    sid = auth_client.post("/api/v1/sessions", json={
        "title": "Meridian Labs - Senior Backend",
        "target_role": "Senior Backend Engineer",
    }).json()["id"]

    for kind, blob, name in (("cv", cv_bytes, "cv.pdf"), ("jd", jd_bytes, "jd.pdf")):
        r = auth_client.post(
            f"/api/v1/sessions/{sid}/documents?kind={kind}",
            files={"file": (name, blob, "application/pdf")},
        )
        assert r.status_code == 202, r.text

    docs = auth_client.get(f"/api/v1/sessions/{sid}/documents").json()
    assert {d["ingest_status"] for d in docs} == {"ready"}, docs
    assert all(d["chunk_count"] > 0 for d in docs)
    return sid


def test_rejects_a_non_pdf_upload(auth_client):
    sid = auth_client.post("/api/v1/sessions", json={"title": "Bad upload"}).json()["id"]
    r = auth_client.post(
        f"/api/v1/sessions/{sid}/documents?kind=cv",
        files={"file": ("notes.pdf", b"this is plain text, not a PDF", "application/pdf")},
    )
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_upload"


def test_analysis_requires_both_documents(auth_client, cv_bytes):
    sid = auth_client.post("/api/v1/sessions", json={"title": "CV only"}).json()["id"]
    auth_client.post(f"/api/v1/sessions/{sid}/documents?kind=cv",
                     files={"file": ("cv.pdf", cv_bytes, "application/pdf")})
    r = auth_client.post(f"/api/v1/sessions/{sid}/analysis")
    assert r.status_code == 409
    assert r.json()["error"] == "documents_not_ready"


def test_full_pipeline(auth_client, ready_session):
    sid = ready_session

    # --- Stage 1: gap analysis, grounded in the CV ------------------------
    report = auth_client.post(f"/api/v1/sessions/{sid}/analysis").json()
    assert 0 <= report["overall_score"] <= 100
    assert len(report["items"]) >= 5

    statuses = {i["status"] for i in report["items"]}
    assert "strong" in statuses, "the CV clearly evidences Python/FastAPI/PostgreSQL"
    assert "missing" in statuses, "the CV has no Kubernetes or Terraform"

    # Every citation must be verbatim from the CV — the grounding contract.
    cv_text = " ".join(
        (__import__("pathlib").Path(__file__).resolve().parent.parent
         / "evals" / "data" / "sample_cv.txt").read_text().split()
    ).lower()
    for item in report["items"]:
        if item["evidence_quote"]:
            assert " ".join(item["evidence_quote"].split()).lower() in cv_text, (
                f"hallucinated citation: {item['evidence_quote']!r}"
            )
        else:
            assert item["status"] in ("missing", "partial")

    # Technologies genuinely absent from the CV must be reported as missing,
    # even when the requirement shares generic words with it ("GraphQL APIs"
    # against a CV full of REST APIs).
    for absent in ("kubernetes", "terraform", "graphql"):
        item = next(i for i in report["items"] if absent in i["requirement"].lower())
        assert item["status"] == "missing", f"{absent} should be missing, got {item}"
        assert item["evidence_quote"] is None

    # Technologies the CV does evidence must be found, with a supporting quote.
    for present in ("postgresql", "python"):
        item = next(i for i in report["items"] if present in i["requirement"].lower())
        assert item["status"] == "strong", f"{present} should be strong, got {item}"
        assert item["evidence_quote"]

    # --- Stage 2: questions derived from the gaps -------------------------
    questions = auth_client.post(
        f"/api/v1/sessions/{sid}/questions?technical=4&behavioural=2"
    ).json()
    assert len(questions) == 6
    assert {q["category"] for q in questions} == {"technical", "behavioural"}
    assert all(q["rationale"] for q in questions), "every question explains why it is asked"
    # The riskiest requirement is asked first.
    assert "kubernetes" in questions[0]["text"].lower()

    # --- Stage 3: evaluation discriminates good from bad ------------------
    technical = next(q for q in questions if q["category"] == "technical")
    strong = auth_client.post(f"/api/v1/questions/{technical['id']}/answers",
                              json={"text": STRONG_ANSWER, "duration_seconds": 95}).json()
    assert strong["evaluation"]["reasoning"], "chain-of-thought trace is stored"
    assert len(strong["evaluation"]["criteria"]) == 5
    assert strong["evaluation"]["follow_up_question"]

    behavioural = next(q for q in questions if q["category"] == "behavioural")
    weak = auth_client.post(f"/api/v1/questions/{behavioural['id']}/answers",
                            json={"text": WEAK_ANSWER}).json()

    assert strong["evaluation"]["overall_score"] > weak["evaluation"]["overall_score"], (
        "a detailed, quantified answer must outscore a vague one"
    )
    assert weak["evaluation"]["rubric"] == "star"
    assert strong["evaluation"]["rubric"] == "technical"

    # --- Stage 4: scorecard aggregates the chain --------------------------
    card = auth_client.post(f"/api/v1/sessions/{sid}/scorecard").json()
    assert 0 <= card["readiness_score"] <= 100
    assert card["readiness_band"]
    assert card["action_items"], "a scorecard must give the candidate something to do"
    assert any(a["priority"] == "high" for a in card["action_items"])
    assert card["competencies"]

    # --- Stage 5: the agent actually uses its tools -----------------------
    coach = auth_client.post(f"/api/v1/sessions/{sid}/coach",
                             json={"message": "What are my biggest gaps for this role?"}).json()
    assert coach["answer"]
    assert any(s["tool"] for s in coach["steps"]), "the agent called at least one tool"
    assert any(s["observation"] for s in coach["steps"])


def test_evaluation_is_reproducible(auth_client, ready_session):
    """Temperature 0 plus a cache means the same answer always scores the same."""
    sid = ready_session
    auth_client.post(f"/api/v1/sessions/{sid}/analysis")
    questions = auth_client.post(
        f"/api/v1/sessions/{sid}/questions?technical=2&behavioural=0").json()
    qid = questions[0]["id"]

    first = auth_client.post(f"/api/v1/questions/{qid}/answers",
                             json={"text": STRONG_ANSWER}).json()
    second = auth_client.post(f"/api/v1/questions/{qid}/answers",
                              json={"text": STRONG_ANSWER}).json()
    assert first["evaluation"]["overall_score"] == second["evaluation"]["overall_score"]


def test_deleting_a_session_purges_its_vectors(auth_client, ready_session):
    from app.rag import store

    sid = ready_session
    sess = auth_client.get(f"/api/v1/sessions/{sid}").json()
    user_id = auth_client.get("/api/v1/auth/me").json()["id"]
    assert store.all_chunks(user_id=user_id, session_id=sid, doc_kind="cv")

    assert auth_client.delete(f"/api/v1/sessions/{sid}").status_code == 204
    assert not store.all_chunks(user_id=user_id, session_id=sid, doc_kind="cv")
    assert auth_client.get(f"/api/v1/sessions/{sid}").status_code == 404


# --- pasted job descriptions ----------------------------------------------

JD_TEXT = (
    "SENIOR BACKEND ENGINEER\n\nREQUIREMENTS\n"
    "Strong commercial experience with Python, ideally with FastAPI.\n"
    "Proven experience designing and operating PostgreSQL databases at scale.\n"
    "Production experience with Kubernetes for container orchestration.\n"
    "Experience building and maintaining CI/CD pipelines.\n"
    "Demonstrated experience mentoring engineers and raising code review standards.\n"
    "\nNICE TO HAVE\nFamiliarity with GraphQL APIs.\n"
)


def test_job_description_can_be_pasted_instead_of_uploaded(auth_client, cv_bytes):
    """The whole pipeline must work when the JD never was a PDF."""
    sid = auth_client.post("/api/v1/sessions", json={"title": "Pasted JD"}).json()["id"]
    auth_client.post(f"/api/v1/sessions/{sid}/documents?kind=cv",
                     files={"file": ("cv.pdf", cv_bytes, "application/pdf")})

    r = auth_client.post(f"/api/v1/sessions/{sid}/documents/text?kind=jd",
                         json={"text": JD_TEXT, "title": "Meridian Labs"})
    assert r.status_code == 202, r.text
    assert r.json()["source"] == "text"

    docs = auth_client.get(f"/api/v1/sessions/{sid}/documents").json()
    assert {d["ingest_status"] for d in docs} == {"ready"}
    pasted = next(d for d in docs if d["kind"] == "jd")
    assert pasted["chunk_count"] > 0
    assert pasted["original_filename"] == "Meridian Labs"

    # The analysis must be as good as it is from a PDF: requirements extracted,
    # verdicts assigned, citations verbatim.
    report = auth_client.post(f"/api/v1/sessions/{sid}/analysis").json()
    assert len(report["items"]) >= 5
    statuses = {i["status"] for i in report["items"]}
    assert "strong" in statuses and "missing" in statuses

    k8s = next(i for i in report["items"] if "kubernetes" in i["requirement"].lower())
    assert k8s["status"] == "missing"
    py = next(i for i in report["items"] if "python" in i["requirement"].lower())
    assert py["status"] == "strong" and py["evidence_quote"]


def test_a_too_short_paste_is_reported_not_analysed(auth_client):
    sid = auth_client.post("/api/v1/sessions", json={"title": "Short"}).json()["id"]
    auth_client.post(f"/api/v1/sessions/{sid}/documents/text?kind=jd",
                     json={"text": "Backend engineer wanted."})
    doc = auth_client.get(f"/api/v1/sessions/{sid}/documents").json()[0]
    assert doc["ingest_status"] == "failed"
    assert "characters" in (doc["ingest_error"] or "")


def test_pasting_replaces_a_previously_uploaded_job_description(auth_client, jd_bytes):
    """Otherwise the old JD's vectors would linger and pollute retrieval."""
    sid = auth_client.post("/api/v1/sessions", json={"title": "Replace"}).json()["id"]
    auth_client.post(f"/api/v1/sessions/{sid}/documents?kind=jd",
                     files={"file": ("jd.pdf", jd_bytes, "application/pdf")})
    auth_client.post(f"/api/v1/sessions/{sid}/documents/text?kind=jd",
                     json={"text": JD_TEXT})

    docs = [d for d in auth_client.get(f"/api/v1/sessions/{sid}/documents").json()
            if d["kind"] == "jd"]
    assert len(docs) == 1
    assert docs[0]["source"] == "text"
