"""SSE endpoints emit well-formed frames and end with the same payload as the
blocking endpoint they mirror.

The value of streaming is entirely in the delivery, so the contract worth
testing is that the delivery does not change the result.
"""

import json

import pytest

from tests.test_pipeline import STRONG_ANSWER, ready_session  # noqa: F401


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """Minimal SSE reader: (event, data) per frame, comments ignored."""
    events = []
    for block in text.split("\n\n"):
        name, payload = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                payload = json.loads(line.removeprefix("data: "))
        if name:
            events.append((name, payload))
    return events


@pytest.fixture
def answered_session(auth_client, ready_session):  # noqa: F811
    sid = ready_session
    auth_client.post(f"/api/v1/sessions/{sid}/analysis")
    auth_client.post(f"/api/v1/sessions/{sid}/questions?technical=2&behavioural=1")
    return sid


def test_answer_stream_reports_stages_then_the_evaluation(auth_client, answered_session):
    sid = answered_session
    qid = auth_client.get(f"/api/v1/sessions/{sid}/questions").json()[0]["id"]

    with auth_client.stream(
        "POST",
        f"/api/v1/questions/{qid}/answers/stream",
        json={"text": STRONG_ANSWER, "duration_seconds": 90},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-accel-buffering"] == "no", "or a proxy buffers it"
        events = parse_sse("".join(response.iter_text()))

    names = [n for n, _ in events]
    assert names[-1] == "done", f"the stream must finish with the result, got {names}"
    assert names.count("stage") >= 3, "the user sees the pipeline advancing"
    assert "error" not in names

    final = events[-1][1]
    assert final["evaluation"]["overall_score"] > 0
    assert final["evaluation"]["criteria"], "the full evaluation arrives, not a summary"


def test_streaming_an_answer_stores_it_like_the_blocking_route(auth_client, answered_session):
    sid = answered_session
    qid = auth_client.get(f"/api/v1/sessions/{sid}/questions").json()[1]["id"]

    with auth_client.stream(
        "POST", f"/api/v1/questions/{qid}/answers/stream",
        json={"text": STRONG_ANSWER, "duration_seconds": 60},
    ) as response:
        streamed = parse_sse("".join(response.iter_text()))[-1][1]

    stored = auth_client.get(f"/api/v1/questions/{qid}/answer").json()
    assert stored["id"] == streamed["id"]
    assert stored["evaluation"]["overall_score"] == streamed["evaluation"]["overall_score"]


def test_cover_letter_streams_tokens_that_rebuild_the_body(auth_client, answered_session):
    sid = answered_session

    with auth_client.stream(
        "POST", f"/api/v1/sessions/{sid}/cover-letter/stream", json={"tone": "plain"},
    ) as response:
        assert response.status_code == 200
        events = parse_sse("".join(response.iter_text()))

    names = [n for n, _ in events]
    assert "token" in names, "prose arrives incrementally"
    assert names[-1] == "done"

    # The pieces the client concatenated must equal the letter that was stored.
    assembled = "".join(d["text"] for n, d in events if n == "token")
    assert assembled == events[-1][1]["body"]

    persisted = auth_client.get(f"/api/v1/sessions/{sid}/cover-letter").json()
    assert persisted["body"] == assembled


def test_a_stream_for_someone_elses_question_is_refused_with_a_status_code(
    client, auth_client, answered_session
):
    """Ownership is checked before the stream opens, so it is a real 404.

    Once a StreamingResponse has begun the status line is already sent and an
    error can only be an event inside a 200 — useless to an HTTP client.
    """
    sid = answered_session
    qid = auth_client.get(f"/api/v1/sessions/{sid}/questions").json()[0]["id"]

    import uuid
    email = f"other-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Other", "password": "testpass123"})
    token = client.post("/api/v1/auth/login", data={
        "username": email, "password": "testpass123"}).json()["access_token"]

    r = client.post(
        f"/api/v1/questions/{qid}/answers/stream",
        json={"text": "x" * 50, "duration_seconds": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_a_streamed_letter_is_prose_not_json(auth_client, answered_session):
    """The streaming path must not stream the JSON envelope.

    The cover letter's normal FORMAT block demands "return ONLY a single JSON
    object". Streamed, that means the reader watches `{"subject": "...` appear
    character by character and the whole object lands in the stored body. The
    offline double hid this by returning only the body text; a real provider
    does what the prompt says.
    """
    sid = answered_session
    with auth_client.stream(
        "POST", f"/api/v1/sessions/{sid}/cover-letter/stream", json={"tone": "plain"},
    ) as response:
        events = parse_sse("".join(response.iter_text()))

    body = "".join(d["text"] for n, d in events if n == "token")
    assert body, "nothing streamed"
    assert not body.lstrip().startswith("{"), f"streamed raw JSON: {body[:80]!r}"
    for marker in ('"subject"', '"claims_used"', '"body":'):
        assert marker not in body, f"JSON envelope leaked into the letter: {marker}"

    stored = auth_client.get(f"/api/v1/sessions/{sid}/cover-letter").json()
    assert stored["body"] == body
    assert not stored["body"].lstrip().startswith("{")
