import pytest
from fastapi.testclient import TestClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"

USER = {"email": "test@example.com", "password": "secret123"}


def test_register_success(client: TestClient):
    res = client.post(REGISTER_URL, json=USER)
    assert res.status_code == 201
    body = res.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_register_duplicate_email(client: TestClient):
    client.post(REGISTER_URL, json=USER)
    res = client.post(REGISTER_URL, json=USER)
    assert res.status_code == 400
    assert "already registered" in res.json()["detail"]


def test_login_success(client: TestClient):
    client.post(REGISTER_URL, json=USER)
    res = client.post(LOGIN_URL, json=USER)
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password(client: TestClient):
    client.post(REGISTER_URL, json=USER)
    res = client.post(LOGIN_URL, json={"email": USER["email"], "password": "wrongpass"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid credentials"


def test_login_unknown_email(client: TestClient):
    res = client.post(LOGIN_URL, json={"email": "nobody@example.com", "password": "x"})
    assert res.status_code == 401


def test_me_authenticated(client: TestClient):
    user = client.post(REGISTER_URL, json=USER)
    token = user.json()["access_token"]
    res = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200 and res.json()["email"] == USER["email"]


def test_me_unauthenticated(client: TestClient):
    res = client.get(ME_URL)
    assert res.status_code == 403
