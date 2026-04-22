"""Integration tests for the meetings API.

Tests transcript upload, action item extraction (mocked LLM), and apply flow.
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

REGISTER_URL = "/api/v1/auth/register"
GOALS_URL = "/api/v1/goals"
MEETINGS_URL = "/api/v1/meetings"

USER = {"email": "meetinguser@example.com", "password": "secret123"}

SAMPLE_TRANSCRIPT = (
    "Alice: We need to finish the login page by EOD Friday. "
    "Bob: I'll handle the API integration, should take about 2 hours. "
    "Alice: Also we need to update the docs, low priority."
)

MOCK_ACTION_ITEMS = [
    {"text": "Finish the login page", "priority": 4, "estimated_hours": 3.0, "assigned_hint": "Alice"},
    {"text": "Handle the API integration", "priority": 3, "estimated_hours": 2.0, "assigned_hint": "Bob"},
    {"text": "Update the docs", "priority": 1, "estimated_hours": None, "assigned_hint": None},
]


@pytest.fixture
def auth_headers(client: TestClient):
    res = client.post(REGISTER_URL, json=USER)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def created_goal(client: TestClient, auth_headers):
    res = client.post(GOALS_URL, json={"title": "Sprint Goal"}, headers=auth_headers)
    return res.json()


@pytest.fixture
def uploaded_meeting(client: TestClient, auth_headers):
    with patch("app.services.meeting_service.extract_action_items", return_value=MOCK_ACTION_ITEMS):
        res = client.post(
            f"{MEETINGS_URL}/upload",
            json={"title": "Sprint Standup", "transcript_text": SAMPLE_TRANSCRIPT, "source": "zoom"},
            headers=auth_headers,
        )
    return res.json()


# ─────────────────────────────────────────────────────────────────────────────
# Upload Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_upload_transcript(client: TestClient, auth_headers):
    with patch("app.services.meeting_service.extract_action_items", return_value=MOCK_ACTION_ITEMS):
        res = client.post(
            f"{MEETINGS_URL}/upload",
            json={"title": "Sprint Standup", "transcript_text": SAMPLE_TRANSCRIPT, "source": "zoom"},
            headers=auth_headers,
        )
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "Sprint Standup"
    assert body["source"] == "zoom"
    assert len(body["action_items"]) == 3


def test_upload_extracts_correct_fields(client: TestClient, auth_headers):
    with patch("app.services.meeting_service.extract_action_items", return_value=MOCK_ACTION_ITEMS):
        res = client.post(
            f"{MEETINGS_URL}/upload",
            json={"transcript_text": SAMPLE_TRANSCRIPT},
            headers=auth_headers,
        )
    assert res.status_code == 201
    items = res.json()["action_items"]
    assert items[0]["raw_text"] == "Finish the login page"
    assert items[0]["priority"] == 4
    assert items[0]["estimated_hours"] == 3.0
    assert items[0]["task_id"] is None  # not yet applied


def test_upload_without_title(client: TestClient, auth_headers):
    with patch("app.services.meeting_service.extract_action_items", return_value=MOCK_ACTION_ITEMS):
        res = client.post(
            f"{MEETINGS_URL}/upload",
            json={"transcript_text": SAMPLE_TRANSCRIPT},
            headers=auth_headers,
        )
    assert res.status_code == 201
    assert res.json()["title"] is None


def test_upload_unauthenticated(client: TestClient):
    res = client.post(
        f"{MEETINGS_URL}/upload",
        json={"transcript_text": SAMPLE_TRANSCRIPT},
    )
    assert res.status_code == 401


def test_upload_llm_failure_returns_empty_items(client: TestClient, auth_headers):
    with patch("app.services.meeting_service.extract_action_items", return_value=[]):
        res = client.post(
            f"{MEETINGS_URL}/upload",
            json={"transcript_text": SAMPLE_TRANSCRIPT},
            headers=auth_headers,
        )
    assert res.status_code == 201
    assert res.json()["action_items"] == []


# ─────────────────────────────────────────────────────────────────────────────
# Retrieve Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_get_transcript(client: TestClient, auth_headers, uploaded_meeting):
    meeting_id = uploaded_meeting["id"]
    res = client.get(f"{MEETINGS_URL}/{meeting_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == meeting_id
    assert len(res.json()["action_items"]) == 3


def test_get_transcript_not_found(client: TestClient, auth_headers):
    fake_id = str(uuid.uuid4())
    res = client.get(f"{MEETINGS_URL}/{fake_id}", headers=auth_headers)
    assert res.status_code == 404


def test_get_transcript_other_user_cannot_access(client: TestClient, uploaded_meeting):
    other_user = {"email": "other@example.com", "password": "secret123"}
    res = client.post(REGISTER_URL, json=other_user)
    token = res.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {token}"}

    meeting_id = uploaded_meeting["id"]
    res = client.get(f"{MEETINGS_URL}/{meeting_id}", headers=other_headers)
    assert res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Apply Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_apply_creates_tasks(client: TestClient, auth_headers, uploaded_meeting, created_goal):
    meeting_id = uploaded_meeting["id"]
    res = client.post(
        f"{MEETINGS_URL}/{meeting_id}/apply",
        json={"goal_id": created_goal["id"]},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tasks_created"] == 3
    assert len(body["task_ids"]) == 3


def test_apply_selective_items(client: TestClient, auth_headers, uploaded_meeting, created_goal):
    items = uploaded_meeting["action_items"]
    selected = [items[0]["id"]]

    meeting_id = uploaded_meeting["id"]
    res = client.post(
        f"{MEETINGS_URL}/{meeting_id}/apply",
        json={"goal_id": created_goal["id"], "action_item_ids": selected},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["tasks_created"] == 1


def test_apply_idempotent(client: TestClient, auth_headers, uploaded_meeting, created_goal):
    """Applying the same meeting twice should not double-create tasks."""
    meeting_id = uploaded_meeting["id"]
    payload = {"goal_id": created_goal["id"]}

    client.post(f"{MEETINGS_URL}/{meeting_id}/apply", json=payload, headers=auth_headers)
    res = client.post(f"{MEETINGS_URL}/{meeting_id}/apply", json=payload, headers=auth_headers)

    assert res.status_code == 200
    assert res.json()["tasks_created"] == 0  # all items already have task_id set


def test_apply_meeting_not_found(client: TestClient, auth_headers, created_goal):
    fake_id = str(uuid.uuid4())
    res = client.post(
        f"{MEETINGS_URL}/{fake_id}/apply",
        json={"goal_id": created_goal["id"]},
        headers=auth_headers,
    )
    assert res.status_code == 404
