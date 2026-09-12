"""The scorecard PDF.

The bytes are not inspected as a design; what is asserted is that it is a real
PDF, that it carries the numbers it claims to, and that it is not reachable
without the session's owner behind it.
"""

import pytest

from tests.test_pipeline import STRONG_ANSWER, ready_session  # noqa: F401


@pytest.fixture
def scored(auth_client, ready_session):  # noqa: F811
    sid = ready_session
    auth_client.post(f"/api/v1/sessions/{sid}/analysis")
    auth_client.post(f"/api/v1/sessions/{sid}/questions?technical=1&behavioural=1")
    qid = auth_client.get(f"/api/v1/sessions/{sid}/questions").json()[0]["id"]
    auth_client.post(f"/api/v1/questions/{qid}/answers",
                     json={"text": STRONG_ANSWER, "duration_seconds": 60})
    card = auth_client.post(f"/api/v1/sessions/{sid}/scorecard").json()
    return sid, card


def test_the_export_is_a_pdf_that_is_offered_as_a_download(auth_client, scored):
    sid, _ = scored
    r = auth_client.get(f"/api/v1/sessions/{sid}/scorecard.pdf")

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-"), "not a PDF"
    assert r.content.rstrip().endswith(b"%%EOF"), "truncated PDF"
    assert "attachment" in r.headers["content-disposition"]
    assert r.headers["content-disposition"].endswith('-scorecard.pdf"')
    assert len(r.content) > 2000, "suspiciously small for a full scorecard"


def test_the_export_carries_the_score_and_the_evidence(auth_client, scored):
    """Extract the text back out and check it matches the stored scorecard."""
    pypdf = pytest.importorskip("pypdf")
    import io

    sid, card = scored
    r = auth_client.get(f"/api/v1/sessions/{sid}/scorecard.pdf")
    text = " ".join(
        page.extract_text() for page in pypdf.PdfReader(io.BytesIO(r.content)).pages
    )

    assert str(card["readiness_score"]) in text
    assert card["readiness_band"] in text
    assert "INTERVIEW COACH" in text

    report = auth_client.get(f"/api/v1/sessions/{sid}/analysis").json()
    quoted = [i for i in report["items"] if i["evidence_quote"]]
    assert quoted, "the fixture should evidence something"
    # The PDF makes the same grounding promise the interface does.
    first_words = " ".join(quoted[0]["evidence_quote"].split()[:4])
    assert first_words in " ".join(text.split())


def test_exporting_before_there_is_a_scorecard_is_refused(auth_client, ready_session):  # noqa: F811
    r = auth_client.get(f"/api/v1/sessions/{ready_session}/scorecard.pdf")
    assert r.status_code == 409
    assert r.json()["error"] == "stage_not_ready"


def test_another_account_cannot_download_it(client, auth_client, scored):
    import uuid
    sid, _ = scored
    email = f"thief-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Thief", "password": "testpass123"})
    token = client.post("/api/v1/auth/login", data={
        "username": email, "password": "testpass123"}).json()["access_token"]

    r = client.get(f"/api/v1/sessions/{sid}/scorecard.pdf",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404, "a CV quote must not be reachable by session id"
