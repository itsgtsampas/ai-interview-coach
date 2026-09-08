"""Seed a demo account with a fully worked session, so the UI has data to show.

Usage:  python scripts/demo_seed.py
Idempotent: re-running resets the demo session.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.db import create_db_and_tables  # noqa: E402
from app.main import app  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "evals" / "data"
EMAIL, PASSWORD = "demo@example.com", "demo1234"

STRONG_ANSWER = (
    "At Nexora I owned the checkout service. The problem was that p99 latency had reached "
    "840ms and we were timing out during peak hours, which was costing us orders. I was "
    "responsible for the whole service, so I profiled it and found we were opening a new "
    "database connection per request. I introduced connection pooling and migrated the hot "
    "path to async I/O in FastAPI. I chose pooling over adding read replicas because the "
    "bottleneck was connection setup, not read capacity, and replicas would have added "
    "replication lag on the checkout path. As a result p99 dropped from 840ms to 210ms over "
    "three weeks, measured on the same dashboard, and checkout timeouts fell by 90 percent."
)
WEAK_ANSWER = (
    "I have not used Kubernetes in production, but I have used Docker a lot so I think it "
    "would be fine and I would pick it up quickly."
)


def main() -> None:
    create_db_and_tables()  # TestClient does not run the lifespan
    client = TestClient(app)
    client.post("/api/v1/auth/register", json={
        "email": EMAIL, "full_name": "Elena Roussou", "password": PASSWORD})
    token = client.post("/api/v1/auth/login", data={
        "username": EMAIL, "password": PASSWORD}).json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    for s in client.get("/api/v1/sessions").json():
        client.delete(f"/api/v1/sessions/{s['id']}")

    sid = client.post("/api/v1/sessions", json={
        "title": "Meridian Labs — Senior Backend Engineer",
        "target_role": "Senior Backend Engineer (Python)",
    }).json()["id"]
    print(f"session {sid}")

    for kind, name in (("cv", "sample_cv.pdf"), ("jd", "sample_jd.pdf")):
        client.post(f"/api/v1/sessions/{sid}/documents?kind={kind}",
                    files={"file": (name, (DATA / name).read_bytes(), "application/pdf")})
    print("documents indexed")

    report = client.post(f"/api/v1/sessions/{sid}/analysis").json()
    print(f"analysis: {report['overall_score']}/100 — {report['verdict']}")

    questions = client.post(f"/api/v1/sessions/{sid}/questions?technical=5&behavioural=3").json()
    print(f"{len(questions)} questions")

    client.post(f"/api/v1/questions/{questions[0]['id']}/answers",
                json={"text": WEAK_ANSWER, "duration_seconds": 48})
    technical = [q for q in questions if q["category"] == "technical"]
    client.post(f"/api/v1/questions/{technical[1]['id']}/answers",
                json={"text": STRONG_ANSWER, "duration_seconds": 132})
    print("2 answers scored")

    card = client.post(f"/api/v1/sessions/{sid}/scorecard").json()
    print(f"scorecard: {card['readiness_score']}/100 — {card['readiness_band']}")
    print(f"\nLog in as {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    main()
