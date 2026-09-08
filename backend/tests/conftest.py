"""Test fixtures.

Environment is redirected to a temporary directory BEFORE the app is imported,
so tests never touch the developer's database, uploads or vector store.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="cvcoach-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["CHROMA_DIR"] = str(_TMP / "chroma")
os.environ["SECRET_KEY"] = "test-secret-key-not-used-in-production"
os.environ["LLM_PROVIDER"] = "stub"
os.environ["EMBEDDING_PROVIDER"] = "stub"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import create_db_and_tables  # noqa: E402
from app.main import app  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "evals" / "data"


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    create_db_and_tables()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    """A client already registered and carrying a bearer token."""
    import uuid

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Test User", "password": "testpass123"
    })
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", data={"username": email, "password": "testpass123"})
    assert r.status_code == 200, r.text
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return client


@pytest.fixture
def cv_bytes() -> bytes:
    return (DATA / "sample_cv.pdf").read_bytes()


@pytest.fixture
def jd_bytes() -> bytes:
    return (DATA / "sample_jd.pdf").read_bytes()
