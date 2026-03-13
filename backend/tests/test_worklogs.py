import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

REGISTER_URL = "/api/v1/auth/register"
GOALS_URL = "/api/v1/goals"
WORKLOGS_URL = "/api/v1/worklogs"

USER_A = {"email": "usera@example.com", "password": "secret123"}
USER_B = {"email": "userb@example.com", "password": "secret123"}
GOAL_PAYLOAD = {"title": "Goal for WorkLog Tests"}
TASK_PAYLOAD = {"title": "Task for WorkLog", "estimated_minutes": 60, "difficulty": 2}


@pytest.fixture
def auth_headers(client: TestClient):
    res = client.post(REGISTER_URL, json=USER_A)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_b(client: TestClient):
    res = client.post(REGISTER_URL, json=USER_B)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def created_task(client: TestClient, auth_headers):
    goal_res = client.post(GOALS_URL, json=GOAL_PAYLOAD, headers=auth_headers)
    goal_id = goal_res.json()["id"]
    task_res = client.post(f"{GOALS_URL}/{goal_id}/tasks", json=TASK_PAYLOAD, headers=auth_headers)
    return task_res.json()


@pytest.fixture
def log_payload(created_task):
    return {
        "task_id": created_task["id"],
        "started_at": "2026-03-13T09:00:00+00:00",
        "ended_at": "2026-03-13T10:00:00+00:00",
        "completed": True,
        "notes": "Finished it",
    }


@pytest.fixture
def created_log(client: TestClient, auth_headers, log_payload):
    res = client.post(WORKLOGS_URL, json=log_payload, headers=auth_headers)
    return res.json()


def test_create_worklog(client: TestClient, auth_headers, log_payload):
    res = client.post(WORKLOGS_URL, json=log_payload, headers=auth_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["completed"] is True
    assert body["notes"] == "Finished it"
    assert "id" in body
    assert "user_id" in body


def test_list_worklogs(client: TestClient, auth_headers, created_log):
    res = client.get(WORKLOGS_URL, headers=auth_headers)
    assert res.status_code == 200
    ids = [log["id"] for log in res.json()]
    assert created_log["id"] in ids


def test_get_worklog(client: TestClient, auth_headers, created_log):
    res = client.get(f"{WORKLOGS_URL}/{created_log['id']}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == created_log["id"]


def test_get_worklog_not_found(client: TestClient, auth_headers):
    res = client.get(f"{WORKLOGS_URL}/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert res.status_code == 404


def test_ownership_isolation(client: TestClient, auth_headers_b, created_log):
    # User B should not see user A's log
    res = client.get(WORKLOGS_URL, headers=auth_headers_b)
    assert res.status_code == 200
    assert res.json() == []


def test_ownership_get_isolation(client: TestClient, auth_headers_b, created_log):
    # User B fetching user A's log by ID gets 404
    res = client.get(f"{WORKLOGS_URL}/{created_log['id']}", headers=auth_headers_b)
    assert res.status_code == 404
