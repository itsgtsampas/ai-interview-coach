def test_register_rejects_weak_password(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "weak@example.com", "full_name": "Weak", "password": "alphabetsonly"
    })
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_request"


def test_duplicate_email_is_conflict(client):
    body = {"email": "dupe@example.com", "full_name": "Dupe", "password": "testpass123"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    r = client.post("/api/v1/auth/register", json=body)
    assert r.status_code == 409
    assert r.json()["error"] == "already_exists"


def test_protected_route_requires_token(client):
    assert client.get("/api/v1/sessions").status_code == 401


def test_me_returns_the_authenticated_user(auth_client):
    r = auth_client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert "@example.com" in r.json()["email"]


def test_other_users_session_is_not_found(client, auth_client):
    created = auth_client.post("/api/v1/sessions", json={"title": "Mine"}).json()

    import uuid
    email = f"other-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Other", "password": "testpass123"})
    token = client.post("/api/v1/auth/login", data={
        "username": email, "password": "testpass123"}).json()["access_token"]

    r = client.get(f"/api/v1/sessions/{created['id']}",
                   headers={"Authorization": f"Bearer {token}"})
    # 404 rather than 403: a 403 would confirm the id exists.
    assert r.status_code == 404
