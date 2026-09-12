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


def _bulleted_jd() -> str:
    from pathlib import Path
    return (Path(__file__).resolve().parent.parent
            / "evals" / "data" / "bulleted_jd.txt").read_text()


def test_a_real_bulleted_posting_yields_real_requirements(auth_client, cv_bytes):
    """Regression: a posting whose bullets carry no full stop.

    This shape previously extracted nothing, fell back to a placeholder
    requirement, and scored every CV 100/100 against it.
    """
    sid = auth_client.post("/api/v1/sessions", json={"title": "Bulleted"}).json()["id"]
    auth_client.post(f"/api/v1/sessions/{sid}/documents?kind=cv",
                     files={"file": ("cv.pdf", cv_bytes, "application/pdf")})
    auth_client.post(f"/api/v1/sessions/{sid}/documents/text?kind=jd",
                     json={"text": _bulleted_jd()})

    report = auth_client.post(f"/api/v1/sessions/{sid}/analysis").json()
    requirements = [i["requirement"] for i in report["items"]]

    assert len(requirements) >= 8, requirements
    assert any("java" in r.lower() for r in requirements)
    assert any("kotlin" in r.lower() for r in requirements)

    # Company blurb, salary and legal boilerplate are not requirements.
    joined = " ".join(requirements).lower()
    for boilerplate in ("compensation", "pln", "job scams", "superapp", "deserve more"):
        assert boilerplate not in joined, f"{boilerplate!r} leaked into the requirements"

    # A Python CV against a Java role must not score as a strong match.
    assert report["overall_score"] < 70, report["overall_score"]
    assert report["counts"]["missing"] > 0


def test_a_posting_with_no_requirements_is_refused_not_scored(auth_client, cv_bytes):
    """Scoring against nothing yields a meaningless perfect match."""
    sid = auth_client.post("/api/v1/sessions", json={"title": "Blurb only"}).json()["id"]
    auth_client.post(f"/api/v1/sessions/{sid}/documents?kind=cv",
                     files={"file": ("cv.pdf", cv_bytes, "application/pdf")})
    auth_client.post(f"/api/v1/sessions/{sid}/documents/text?kind=jd", json={"text": (
        "About the job\nAbout Northwind\n"
        "People deserve more from their money, and we are building the financial "
        "superapp to give it to them. We are growing fast and we would love to "
        "hear from you. Our culture is built on trust, ownership and speed.\n"
        "Important notice for candidates\nJob scams are on the rise.\n")})

    r = auth_client.post(f"/api/v1/sessions/{sid}/analysis")
    assert r.status_code == 422
    assert r.json()["error"] == "no_requirements_found"


def test_traits_a_cv_cannot_show_are_excluded_from_the_score(auth_client, cv_bytes):
    """A CV cannot evidence "excellent communication skills".

    Counting such a requirement as missing marks the candidate down for a
    limitation of the medium, not of their experience, so it is excluded from
    the score and routed to the behavioural questions instead.
    """
    sid = auth_client.post("/api/v1/sessions", json={"title": "Traits"}).json()["id"]
    auth_client.post(f"/api/v1/sessions/{sid}/documents?kind=cv",
                     files={"file": ("cv.pdf", cv_bytes, "application/pdf")})
    auth_client.post(f"/api/v1/sessions/{sid}/documents/text?kind=jd", json={"text": (
        "SENIOR BACKEND ENGINEER\n\nWhat you'll need\n"
        "Fluency with Python and FastAPI\n"
        "Proven experience operating PostgreSQL at scale\n"
        "Excellent communication and organisational skills\n"
        "The ability to work well as part of a team in a fast-paced environment\n"
        "To be a quick learner with an ambitious attitude\n")})

    report = auth_client.post(f"/api/v1/sessions/{sid}/analysis").json()
    kinds = {i["requirement"]: i["kind"] for i in report["items"]}

    behavioural = [r for r, k in kinds.items() if k == "behavioural"]
    assert len(behavioural) == 3, kinds
    assert all(
        any(w in r.lower() for w in ("communication", "team", "learner"))
        for r in behavioural
    )
    # Naming a technology keeps a requirement in the score.
    assert kinds["Fluency with Python and FastAPI"] == "evidenceable"

    # The three traits are unevidenced, but the score is computed only over the
    # two evidenceable requirements, both of which this CV covers.
    assert report["overall_score"] == 100, report["overall_score"]

    questions = auth_client.post(
        f"/api/v1/sessions/{sid}/questions?technical=2&behavioural=3").json()
    behavioural_qs = [q for q in questions if q["category"] == "behavioural"]
    assert len(behavioural_qs) == 3
    # Each behavioural question is tied to a trait the posting actually named,
    # rather than to the generic bank.
    assert {q["linked_requirement"] for q in behavioural_qs} == set(behavioural)


def test_work_a_cv_can_show_still_counts(auth_client, cv_bytes, jd_bytes):
    """Mentoring and collaboration describe things a person did, so they stay in
    the score. Only dispositions are excluded."""
    sid = auth_client.post("/api/v1/sessions", json={"title": "Evidenceable"}).json()["id"]
    auth_client.post(f"/api/v1/sessions/{sid}/documents?kind=cv",
                     files={"file": ("cv.pdf", cv_bytes, "application/pdf")})
    auth_client.post(f"/api/v1/sessions/{sid}/documents?kind=jd",
                     files={"file": ("jd.pdf", jd_bytes, "application/pdf")})
    report = auth_client.post(f"/api/v1/sessions/{sid}/analysis").json()

    mentoring = next(i for i in report["items"] if "mentoring" in i["requirement"].lower())
    assert mentoring["kind"] == "evidenceable"
    assert mentoring["status"] == "strong"


NETCOMPANY_JD = """About the job
Company Description
We are dedicated to responsible digitalisation across Europe.

Job Description
Joining us as a Software Engineer, you will build back-end systems.

Qualifications
What would make you a fit for the role:
Degree in Computer Science, Software Engineering or a related discipline
Experience in
Java
Spring Framework
Spring Boot
Docker
Excellent communication skills
Fluency in English
It would also be a plus if you match some of the following:
Familiarity with Kubernetes
Knowledge of Apache Kafka
Experience in React

Additional Information
Being a part of the team, you will be provided with:
The opportunity to work in a modern environment & in a hybrid working model
A seamless onboarding experience and a buddy to support you
A competitive compensation & benefits package
Health and life insurance program
"""


def test_a_posting_of_bare_technology_names(auth_client, cv_bytes):
    """Regression from a real Netcompany posting.

    Its requirements are bare technology names under a colon-terminated lead-in,
    followed by a benefits section. Previously the lead-ins and the benefits
    were scored as requirements while "Java", "Docker" and "Spring Boot" were
    discarded for being too short — the requirements that matter most.
    """
    sid = auth_client.post("/api/v1/sessions", json={"title": "Netcompany"}).json()["id"]
    auth_client.post(f"/api/v1/sessions/{sid}/documents?kind=cv",
                     files={"file": ("cv.pdf", cv_bytes, "application/pdf")})
    auth_client.post(f"/api/v1/sessions/{sid}/documents/text?kind=jd",
                     json={"text": NETCOMPANY_JD})

    report = auth_client.post(f"/api/v1/sessions/{sid}/analysis").json()
    reqs = [i["requirement"] for i in report["items"]]
    joined = " ".join(reqs).lower()

    # Bare technology names survive.
    for tech in ("Java", "Spring Framework", "Spring Boot", "Docker"):
        assert any(tech.lower() in r.lower() for r in reqs), f"{tech} was dropped: {reqs}"

    # Lead-ins, benefits and boilerplate do not become requirements.
    for noise in ("would make you a fit", "plus if you match", "provided with",
                  "onboarding", "insurance", "compensation", "hybrid working"):
        assert noise not in joined, f"{noise!r} was scored as a requirement"

    # The nice-to-have lead-in still switches the bucket.
    kubernetes = next(i for i in report["items"] if "kubernetes" in i["requirement"].lower())
    assert kubernetes["category"] == "nice_to_have"


def test_a_skills_list_entry_counts_as_evidence(auth_client, jd_bytes):
    """A CV listing "React.js" evidences React, even though the line is short.

    The sentence splitter discarded anything under 15 characters, which is
    exactly the length of a skills-list entry naming a technology.
    """
    from app.textutil import sentences

    found = sentences("› HTML · CSS · JSP\n› React.js\n› Angular.js")
    assert any("React.js" in s for s in found), found


def test_a_descriptive_sentence_is_preferred_over_a_list_entry():
    """Both cover the requirement; only one says what was done with it."""
    from app.textutil import best_evidence, build_idf

    passages = [
        "SKILLS\nSpring Boot",
        "Developed a Spring Boot microservice implementing an IVR calling flow "
        "for a national telecoms provider.",
    ]
    idf = build_idf(passages)
    quotes = [best_evidence("Spring Boot", p, idf) for p in passages]
    assert all(q[2] for q in quotes), "both should carry the decisive term"
    assert len(quotes[0][0]) < 25 and len(quotes[1][0]) >= 25


# --- profile ---------------------------------------------------------------

def test_a_new_session_starts_from_the_profile_cv(auth_client, cv_bytes, jd_bytes):
    """A CV does not change per application, so it should not be re-uploaded."""
    r = auth_client.post("/api/v1/profile/cv",
                         files={"file": ("mycv.pdf", cv_bytes, "application/pdf")})
    assert r.status_code == 201, r.text
    assert r.json()["has_cv"] and r.json()["cv_filename"] == "mycv.pdf"

    sid = auth_client.post("/api/v1/sessions", json={"title": "From profile"}).json()["id"]
    docs = auth_client.get(f"/api/v1/sessions/{sid}/documents").json()
    cv = next(d for d in docs if d["kind"] == "cv")
    assert cv["ingest_status"] == "ready"
    assert cv["chunk_count"] > 0
    assert cv["original_filename"] == "mycv.pdf"

    # It is a copy: replacing it inside the session leaves the profile alone.
    auth_client.post(f"/api/v1/sessions/{sid}/documents?kind=cv",
                     files={"file": ("other.pdf", jd_bytes, "application/pdf")})
    assert auth_client.get("/api/v1/profile").json()["cv_filename"] == "mycv.pdf"
    session_cv = next(d for d in auth_client.get(f"/api/v1/sessions/{sid}/documents").json()
                      if d["kind"] == "cv")
    assert session_cv["original_filename"] == "other.pdf"


def test_a_session_can_opt_out_of_the_profile_cv(auth_client, cv_bytes):
    auth_client.post("/api/v1/profile/cv",
                     files={"file": ("mycv.pdf", cv_bytes, "application/pdf")})
    sid = auth_client.post("/api/v1/sessions", json={
        "title": "Different CV", "use_profile_cv": False}).json()["id"]
    assert auth_client.get(f"/api/v1/sessions/{sid}/documents").json() == []


def test_profile_details_round_trip(auth_client):
    r = auth_client.put("/api/v1/profile", json={
        "headline": "Software Engineer", "seniority": "mid", "years_experience": 3,
        "target_roles": "Backend Engineer", "location": "Athens, Greece",
        "languages": "Greek (native), English (B2)",
        "github_url": "https://github.com/example",
        "date_of_birth": "1998-04-12", "gender": "male",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["headline"] == "Software Engineer"
    assert body["age"] == 28  # derived, not stored
    assert auth_client.get("/api/v1/profile").json()["years_experience"] == 3


def test_demographics_never_reach_a_prompt(auth_client):
    """Age and gender are protected characteristics that say nothing about
    whether a CV meets a requirement. They are stored, and excluded by
    construction from the only profile text the pipeline can see."""
    from app.models import UserProfile
    from datetime import date

    profile = UserProfile(
        user_id=1, headline="Software Engineer", years_experience=3,
        date_of_birth=date(1990, 1, 1), gender="female", nationality="Greek",
        phone="+30 690 000 0000",
    )
    context = profile.profile_context()
    assert "Software Engineer" in context
    for leaked in ("1990", "female", "Greek", "690"):
        assert leaked not in context, f"{leaked!r} reached the model context"
