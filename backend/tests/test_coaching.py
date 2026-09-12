"""The two generative writing stages, and the one thing both must never do.

A CV bullet generator and a cover letter generator are the easiest places in
this product to produce something that reads beautifully and is false. Both
stages are built so that the false version is unreachable rather than merely
discouraged, and these tests pin that down.
"""

import pytest

from tests.test_pipeline import STRONG_ANSWER, ready_session  # noqa: F401


@pytest.fixture
def analysed(auth_client, ready_session):  # noqa: F811
    sid = ready_session
    report = auth_client.post(f"/api/v1/sessions/{sid}/analysis").json()
    return sid, report


def test_a_bullet_for_a_missing_skill_is_a_template_not_a_claim(auth_client, analysed):
    sid, report = analysed
    gap = next(i for i in report["items"] if i["status"] == "missing")

    r = auth_client.post(f"/api/v1/sessions/{sid}/match-items/{gap['id']}/rewrite")
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["placeholders"], "a bullet with no gaps to fill is an invented claim"
    for slot in body["placeholders"]:
        assert slot in body["bullet"], f"{slot} is advertised but not in the bullet"
    assert body["if_you_cannot"], "the honest alternative is part of the output"


def test_a_bullet_never_invents_a_number(auth_client, analysed):
    """Every digit in the suggestion must be inside a placeholder.

    This is the specific failure the stage exists to prevent: "reduced p99 by
    45%" for someone who has never measured p99.
    """
    import re

    sid, report = analysed
    for gap in [i for i in report["items"] if i["status"] == "missing"][:3]:
        body = auth_client.post(
            f"/api/v1/sessions/{sid}/match-items/{gap['id']}/rewrite"
        ).json()
        outside = re.sub(r"\[[^\]]*\]", "", body["bullet"])
        assert not re.search(r"\d", outside), (
            f"invented a figure outside a placeholder: {body['bullet']!r}"
        )


def test_an_evidenced_requirement_is_refused(auth_client, analysed):
    sid, report = analysed
    strong = next(i for i in report["items"] if i["status"] == "strong")
    r = auth_client.post(f"/api/v1/sessions/{sid}/match-items/{strong['id']}/rewrite")
    assert r.status_code == 409
    assert "already evidenced" in r.json()["message"]


def test_a_rewrite_is_computed_once_and_reused(auth_client, analysed):
    sid, report = analysed
    gap = next(i for i in report["items"] if i["status"] == "missing")
    first = auth_client.post(f"/api/v1/sessions/{sid}/match-items/{gap['id']}/rewrite").json()
    second = auth_client.post(f"/api/v1/sessions/{sid}/match-items/{gap['id']}/rewrite").json()
    assert first["id"] == second["id"], "regenerating would spend a model call per view"

    listed = auth_client.get(f"/api/v1/sessions/{sid}/rewrites").json()
    assert [s["id"] for s in listed] == [first["id"]]


def test_a_cover_letter_only_claims_what_the_cv_evidenced(auth_client, analysed):
    sid, report = analysed
    r = auth_client.post(f"/api/v1/sessions/{sid}/cover-letter", json={"tone": "plain"})
    assert r.status_code == 201, r.text
    letter = r.json()

    evidenced = {i["requirement"] for i in report["items"] if i["status"] == "strong"}
    assert set(letter["claims_used"]) <= evidenced, (
        "the letter cited a requirement the CV did not evidence"
    )

    # A technology the CV lacks may be named once, in the acknowledgement
    # sentence. What it may never do is appear in a sentence that asserts the
    # candidate has it - so every sentence mentioning one must be negated.
    negations = ("not yet", "have not", "no experience", "nearest")
    for absent in ("kubernetes", "terraform", "graphql"):
        item = next((i for i in report["items"] if absent in i["requirement"].lower()), None)
        if item is None or item["status"] != "missing":
            continue
        for sentence in letter["body"].lower().replace("\n", " ").split("."):
            if absent in sentence:
                assert any(n in sentence for n in negations), (
                    f"claimed {absent} as experience: {sentence.strip()!r}"
                )


def test_a_cover_letter_needs_the_analysis_first(auth_client):
    sid = auth_client.post("/api/v1/sessions", json={"title": "Empty"}).json()["id"]
    r = auth_client.post(f"/api/v1/sessions/{sid}/cover-letter", json={"tone": "plain"})
    assert r.status_code == 409
    assert r.json()["error"] == "stage_not_ready"


def test_the_tone_changes_the_letter(auth_client, analysed):
    sid, _ = analysed
    plain = auth_client.post(
        f"/api/v1/sessions/{sid}/cover-letter", json={"tone": "plain"}).json()["body"]
    formal = auth_client.post(
        f"/api/v1/sessions/{sid}/cover-letter", json={"tone": "formal"}).json()["body"]
    assert plain != formal
