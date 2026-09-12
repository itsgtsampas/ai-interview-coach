"""Cross-session aggregation, and the insight it exists to produce.

A gap in one posting is a mismatch. The same gap across several is the thing
worth learning, and no single session can see it.
"""

import pytest

from app.services.progress import _gap_key
from tests.test_pipeline import STRONG_ANSWER, ready_session  # noqa: F401


@pytest.mark.parametrize("a,b", [
    ("Experience with Kubernetes in production", "Kubernetes (must have)"),
    ("Strong Java and Spring Boot", "Java / Spring Boot experience"),
    ("Production experience with Terraform", "Terraform or similar IaC"),
])
def test_the_same_gap_phrased_differently_groups_together(a, b):
    assert _gap_key(a) == _gap_key(b) != ""


def test_boilerplate_that_is_not_a_learnable_gap_is_dropped():
    """"5+ years of experience" is not something to go and learn this month."""
    assert _gap_key("5+ years of experience") == ""


def test_progress_is_empty_but_valid_for_a_new_account(auth_client):
    body = auth_client.get("/api/v1/progress").json()
    assert body["sessions_total"] >= 0
    assert body["has_trend"] is False
    assert body["recurring_gaps"] == []


def test_a_gap_repeated_across_sessions_is_surfaced(auth_client, cv_bytes, jd_bytes):
    """Two applications, same CV, same posting: every gap recurs in both."""
    for title in ("Application one", "Application two"):
        sid = auth_client.post("/api/v1/sessions", json={
            "title": title, "target_role": "Backend Engineer", "use_profile_cv": False,
        }).json()["id"]
        for kind, blob in (("cv", cv_bytes), ("jd", jd_bytes)):
            auth_client.post(f"/api/v1/sessions/{sid}/documents?kind={kind}",
                             files={"file": (f"{kind}.pdf", blob, "application/pdf")})
        auth_client.post(f"/api/v1/sessions/{sid}/analysis")

    body = auth_client.get("/api/v1/progress").json()
    assert body["sessions_total"] >= 2
    assert body["recurring_gaps"], "the same missing skill in both should surface"

    top = body["recurring_gaps"][0]
    assert top["missing_in"] >= 2
    assert len(top["sessions"]) == top["missing_in"], "each session counted once"
    assert body["mean_match"] is not None


def test_a_trend_needs_more_than_two_points(auth_client, ready_session):  # noqa: F811
    """One scored session is a number, not a trend, and the flag says so."""
    sid = ready_session
    auth_client.post(f"/api/v1/sessions/{sid}/analysis")
    auth_client.post(f"/api/v1/sessions/{sid}/questions?technical=1&behavioural=1")
    qid = auth_client.get(f"/api/v1/sessions/{sid}/questions").json()[0]["id"]
    auth_client.post(f"/api/v1/questions/{qid}/answers",
                     json={"text": STRONG_ANSWER, "duration_seconds": 60})
    auth_client.post(f"/api/v1/sessions/{sid}/scorecard")

    body = auth_client.get("/api/v1/progress").json()
    assert body["sessions_scored"] >= 1
    assert body["latest_readiness"] is not None
    assert body["has_trend"] is (body["sessions_scored"] >= 3)


def test_progress_is_scoped_to_the_caller(client, auth_client, cv_bytes, jd_bytes):
    import uuid
    auth_client.post("/api/v1/sessions", json={"title": "Mine", "use_profile_cv": False})

    email = f"stranger-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Stranger", "password": "testpass123"})
    token = client.post("/api/v1/auth/login", data={
        "username": email, "password": "testpass123"}).json()["access_token"]

    body = client.get("/api/v1/progress",
                      headers={"Authorization": f"Bearer {token}"}).json()
    assert body["sessions_total"] == 0, "another account's sessions must not leak in"
