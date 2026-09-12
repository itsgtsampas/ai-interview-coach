"""The ceilings actually fire.

conftest disables rate limiting for the suite, because the other tests make more
requests per second than any ceiling should allow. These tests switch the
limiter back on around themselves, so the mechanism is exercised without every
other test having to budget for it.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ratelimit import limiter


@pytest.fixture
def limited():
    """The limiter, on, with a clean slate before and after."""
    limiter.reset()
    limiter.enabled = True
    yield TestClient(app)
    limiter.enabled = False
    limiter.reset()


def test_login_is_capped_and_says_so(limited):
    """Six password attempts in a minute is a password list, not a typo."""
    payload = {"username": "nobody@example.com", "password": "wrong-password"}

    codes = [
        limited.post("/api/v1/auth/login", data=payload).status_code
        for _ in range(6)
    ]

    assert codes[:5] == [400] * 5, "the first five attempts are answered normally"
    assert codes[5] == 429, f"the sixth should be refused, got {codes}"

    body = limited.post("/api/v1/auth/login", data=payload).json()
    assert body["error"] == "rate_limited"
    assert "request_id" in body, "429 keeps the application's single error shape"


def test_the_refusal_tells_the_client_when_to_retry(limited):
    payload = {"username": "nobody2@example.com", "password": "wrong-password"}
    for _ in range(6):
        response = limited.post("/api/v1/auth/login", data=payload)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"


def test_an_authenticated_ceiling_is_per_account_not_per_address(limited):
    """Two users behind one address must not share a budget.

    Both clients here come from the same test address, so if the key were the
    address the second user would inherit the first user's spend.
    """
    tokens = []
    for _ in range(2):
        email = f"tenant-{uuid.uuid4().hex[:8]}@example.com"
        limited.post("/api/v1/auth/register", json={
            "email": email, "full_name": "Tenant", "password": "testpass123"
        })
        r = limited.post("/api/v1/auth/login",
                         data={"username": email, "password": "testpass123"})
        assert r.status_code == 200, r.text
        tokens.append(r.json()["access_token"])
        limiter.reset()  # clear the address-keyed login budget between sign-ups

    first, second = tokens
    sid = limited.post(
        "/api/v1/sessions", json={"title": "Tenant one"},
        headers={"Authorization": f"Bearer {first}"},
    ).json()["id"]

    # Spend the first account's generate budget on a session it owns.
    for _ in range(31):
        limited.post(f"/api/v1/sessions/{sid}/analysis",
                     headers={"Authorization": f"Bearer {first}"})

    exhausted = limited.post(f"/api/v1/sessions/{sid}/analysis",
                             headers={"Authorization": f"Bearer {first}"})
    assert exhausted.status_code == 429, "the first account is out of budget"

    # The second account's own session must still be reachable.
    other = limited.post(
        "/api/v1/sessions", json={"title": "Tenant two"},
        headers={"Authorization": f"Bearer {second}"},
    )
    assert other.status_code == 201, "the second account was not charged for the first"
