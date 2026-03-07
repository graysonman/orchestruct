import pytest
from fastapi.testclient import TestClient

REGISTER_URL = "/api/v1/auth/register"
GOALS_URL = "/api/v1/goals"
PLANS_URL = "/api/v1/plans"

USER = {"email": "planuser@example.com", "password": "secret123"}
GOAL_PAYLOAD = {"title": "Plan Goal"}
TASK_PAYLOAD = {"title": "Plan Task", "estimated_minutes": 60, "difficulty": 2, "due_date": "2026-03-14"}
WINDOW_PAYLOAD = {"planning_window_start": "2026-03-10", "planning_window_end": "2026-03-14"}


@pytest.fixture
def auth_headers(client: TestClient):
    res = client.post(REGISTER_URL, json=USER)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def created_goal(client: TestClient, auth_headers):
    res = client.post(GOALS_URL, json=GOAL_PAYLOAD, headers=auth_headers)
    return res.json()


@pytest.fixture
def created_task(client: TestClient, auth_headers, created_goal):
    tasks_url = f"{GOALS_URL}/{created_goal['id']}/tasks"
    res = client.post(tasks_url, json=TASK_PAYLOAD, headers=auth_headers)
    return res.json()


@pytest.fixture
def generated_plan(client: TestClient, auth_headers, created_task):
    res = client.post(f"{PLANS_URL}/generate", json=WINDOW_PAYLOAD, headers=auth_headers)
    return res.json()


def test_generate_plan(client: TestClient, auth_headers, created_task):
    res = client.post(f"{PLANS_URL}/generate", json=WINDOW_PAYLOAD, headers=auth_headers)
    assert res.status_code == 201
    assert res.json()["status"] == "proposed"
    assert isinstance(res.json()["items"], list)


def test_generate_plan_unauthenticated(client: TestClient, created_task):
    res = client.post(f"{PLANS_URL}/generate", json=WINDOW_PAYLOAD)
    assert res.status_code == 403


def test_get_plan(client: TestClient, auth_headers, generated_plan):
    res = client.get(f"{PLANS_URL}/{generated_plan['id']}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == generated_plan["id"]


def test_approve_plan(client: TestClient, auth_headers, generated_plan):
    res = client.post(f"{PLANS_URL}/{generated_plan['id']}/approve", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "approved"


def test_reject_plan(client: TestClient, auth_headers, generated_plan):
    res = client.post(f"{PLANS_URL}/{generated_plan['id']}/reject", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "invalidated"


def test_generate_empty_plan(client: TestClient, auth_headers, created_goal):
    res = client.post(f"{PLANS_URL}/generate", json=WINDOW_PAYLOAD, headers=auth_headers)
    assert res.status_code == 201
    assert res.json()["items"] == []
