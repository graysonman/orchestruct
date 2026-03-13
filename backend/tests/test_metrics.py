import pytest
from fastapi.testclient import TestClient

REGISTER_URL = "/api/v1/auth/register"
METRICS_URL = "/api/v1/metrics/me"

USER = {"email": "metricsuser@example.com", "password": "secret123"}


@pytest.fixture
def auth_headers(client: TestClient):
    res = client.post(REGISTER_URL, json=USER)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_returns_401(client: TestClient):
    res = client.get(METRICS_URL)
    assert res.status_code == 401


def test_fresh_user_gets_default_metrics(client: TestClient, auth_headers):
    res = client.get(METRICS_URL, headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["completion_rate"] == 0.0
    assert body["estimation_bias_multiplier"] == 1.0
    assert "id" in body
    assert "user_id" in body


def test_calling_twice_returns_same_id(client: TestClient, auth_headers):
    res1 = client.get(METRICS_URL, headers=auth_headers)
    res2 = client.get(METRICS_URL, headers=auth_headers)
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["id"] == res2.json()["id"]
