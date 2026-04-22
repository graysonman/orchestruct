import pytest
from fastapi.testclient import TestClient

GOALS_URL = "/api/v1/goals"
REGISTER_URL = "/api/v1/auth/register"

USER = {"email": "goaluser@example.com", "password": "secret123"}
GOAL_PAYLOAD = {"title": "Learn FastAPI", "priority_weight": 1.5}


@pytest.fixture
def auth_headers(client: TestClient):
    res = client.post(REGISTER_URL, json=USER)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def created_goal(client: TestClient, auth_headers):
    res = client.post(GOALS_URL, json=GOAL_PAYLOAD, headers=auth_headers)
    return res.json()


def test_create_goal(client: TestClient, auth_headers):
    res = client.post(GOALS_URL, json=GOAL_PAYLOAD, headers=auth_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == GOAL_PAYLOAD["title"]
    assert body["priority_weight"] == GOAL_PAYLOAD["priority_weight"]
    assert "id" in body


def test_create_goal_unauthenticated(client: TestClient):
    res = client.post(GOALS_URL, json=GOAL_PAYLOAD)
    assert res.status_code == 401


def test_list_goals(client: TestClient, auth_headers, created_goal):
    res = client.get(GOALS_URL, headers=auth_headers)
    assert res.status_code == 200
    ids = [g["id"] for g in res.json()]
    assert created_goal["id"] in ids


def test_get_goal(client: TestClient, auth_headers, created_goal):
    res = client.get(f"{GOALS_URL}/{created_goal['id']}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == created_goal["id"]


def test_get_goal_not_found(client: TestClient, auth_headers):
    res = client.get(f"{GOALS_URL}/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert res.status_code == 404


def test_update_goal(client: TestClient, auth_headers, created_goal):
    res = client.patch(
        f"{GOALS_URL}/{created_goal['id']}",
        json={"title": "Updated Title"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["title"] == "Updated Title"


def test_delete_goal(client: TestClient, auth_headers, created_goal):
    res = client.delete(f"{GOALS_URL}/{created_goal['id']}", headers=auth_headers)
    assert res.status_code == 204
    res = client.get(f"{GOALS_URL}/{created_goal['id']}", headers=auth_headers)
    assert res.status_code == 404
