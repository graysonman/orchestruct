import pytest
from fastapi.testclient import TestClient

REGISTER_URL = "/api/v1/auth/register"
GOALS_URL = "/api/v1/goals"

USER = {"email": "taskuser@example.com", "password": "secret123"}
GOAL_PAYLOAD = {"title": "Goal for Tasks"}
TASK_PAYLOAD = {"title": "First Task", "estimated_minutes": 30, "difficulty": 2}


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
def tasks_url(created_goal):
    return f"{GOALS_URL}/{created_goal['id']}/tasks"


@pytest.fixture
def created_task(client: TestClient, auth_headers, tasks_url):
    res = client.post(tasks_url, json=TASK_PAYLOAD, headers=auth_headers)
    return res.json()

def test_create_task(client: TestClient, auth_headers, tasks_url):
    res = client.post(tasks_url, json=TASK_PAYLOAD, headers=auth_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == TASK_PAYLOAD["title"]
    assert body["estimated_minutes"] == TASK_PAYLOAD["estimated_minutes"]
    assert body["difficulty"] == TASK_PAYLOAD["difficulty"]
    assert "id" in body

def test_list_tasks(client: TestClient, auth_headers, created_task, tasks_url):
    res = client.get(tasks_url, headers=auth_headers)
    assert res.status_code == 200
    ids = [t["id"] for t in res.json()]
    assert created_task["id"] in ids

def test_get_task(client: TestClient, auth_headers, created_task, tasks_url):
    res = client.get(f"{tasks_url}/{created_task['id']}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == created_task["id"]

def test_get_task_not_found(client: TestClient, auth_headers, tasks_url):
    res = client.get(f"{tasks_url}/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert res.status_code == 404

def test_update_task(client: TestClient, auth_headers, created_task, tasks_url):
    res = client.patch(f"{tasks_url}/{created_task['id']}",json={"title": "Updated Title"}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["title"] == "Updated Title"

def test_delete_task(client:TestClient, auth_headers, created_task, tasks_url):
    res = client.delete(f"{tasks_url}/{created_task['id']}", headers=auth_headers)
    assert res.status_code == 204
    res = client.get(f"{tasks_url}/{created_task['id']}", headers=auth_headers)
    assert res.status_code == 404