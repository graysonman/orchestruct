"""Integration tests for the plans API.

Tests plan generation, approval workflows, and validation.
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

REGISTER_URL = "/api/v1/auth/register"
GOALS_URL = "/api/v1/goals"
PLANS_URL = "/api/v1/plans"

USER = {"email": "planuser@example.com", "password": "secret123"}
GOAL_PAYLOAD = {"title": "Plan Goal"}

# Use dynamic dates relative to today
today = date.today()
TASK_PAYLOAD = {
    "title": "Plan Task",
    "estimated_minutes": 60,
    "difficulty": 2,
    "due_date": str(today + timedelta(days=4)),
}
WINDOW_PAYLOAD = {
    "planning_window_start": str(today),
    "planning_window_end": str(today + timedelta(days=4)),
}


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
    assert res.status_code == 401  # Unauthorized (not authenticated)


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


# ─────────────────────────────────────────────────────────────────────────────
# Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_plan_window_in_past(client: TestClient, auth_headers, created_task):
    """Planning window starting in the past should return 422."""
    past_date = str(date.today() - timedelta(days=1))
    payload = {
        "planning_window_start": past_date,
        "planning_window_end": str(date.today() + timedelta(days=3)),
    }
    res = client.post(f"{PLANS_URL}/generate", json=payload, headers=auth_headers)
    assert res.status_code == 422
    assert "errors" in res.json()["detail"]


def test_generate_plan_window_too_long(client: TestClient, auth_headers, created_task):
    """Planning window exceeding 14 days should return 422."""
    payload = {
        "planning_window_start": str(date.today()),
        "planning_window_end": str(date.today() + timedelta(days=20)),
    }
    res = client.post(f"{PLANS_URL}/generate", json=payload, headers=auth_headers)
    assert res.status_code == 422
    assert "errors" in res.json()["detail"]


def test_generate_plan_window_end_before_start(client: TestClient, auth_headers, created_task):
    """Planning window with end before start should return 422."""
    payload = {
        "planning_window_start": str(date.today() + timedelta(days=5)),
        "planning_window_end": str(date.today()),
    }
    res = client.post(f"{PLANS_URL}/generate", json=payload, headers=auth_headers)
    assert res.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Enhanced Risk Metrics Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_plan_has_enhanced_risk_summary(client: TestClient, auth_headers, created_task):
    """Generated plan should include enhanced risk metrics."""
    res = client.post(f"{PLANS_URL}/generate", json=WINDOW_PAYLOAD, headers=auth_headers)
    assert res.status_code == 201
    risk = res.json()["risk_summary"]

    # Backward compatible fields
    assert "scheduled" in risk
    assert "unscheduled" in risk
    assert "avg_risk" in risk

    # Quality score (your implementation!)
    assert "quality_score" in risk
    assert 0 <= risk["quality_score"] <= 100

    # New enhanced fields
    assert "deadline_slack_ratio" in risk
    assert "overload_ratio" in risk
    assert "context_switching_count" in risk
    assert "burnout_likelihood" in risk
    assert "critical_days" in risk
    assert "deadline_warnings" in risk
    assert "recommendations" in risk


def test_plan_items_have_enriched_rationale(client: TestClient, auth_headers, created_task):
    """Scheduled items should include enriched rationale."""
    res = client.post(f"{PLANS_URL}/generate", json=WINDOW_PAYLOAD, headers=auth_headers)
    assert res.status_code == 201
    items = res.json()["items"]

    # Should have scheduled the task
    assert len(items) > 0

    rationale = items[0]["rationale"]

    # Backward compatible fields
    assert "score" in rationale
    assert "placed_on" in rationale
    assert "reason" in rationale

    # New enriched fields
    assert "score_breakdown" in rationale
    assert "risk_factors" in rationale
    assert "warnings" in rationale


def test_plan_risk_summary_recommendations(client: TestClient, auth_headers, created_goal):
    """Empty plan should have helpful recommendations."""
    # Generate plan with no tasks
    res = client.post(f"{PLANS_URL}/generate", json=WINDOW_PAYLOAD, headers=auth_headers)
    assert res.status_code == 201

    risk = res.json()["risk_summary"]
    # Should have a recommendation about no tasks
    assert isinstance(risk["recommendations"], list)


# ─────────────────────────────────────────────────────────────────────────────
# Multiple Tasks Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_plan_multiple_tasks_from_different_goals(client: TestClient, auth_headers):
    """Plan should track context switches between goals."""
    # Create first goal with task
    res = client.post(GOALS_URL, json={"title": "Goal A"}, headers=auth_headers)
    goal_a = res.json()
    client.post(
        f"{GOALS_URL}/{goal_a['id']}/tasks",
        json={"title": "Task A1", "estimated_minutes": 60, "difficulty": 2},
        headers=auth_headers,
    )

    # Create second goal with task
    res = client.post(GOALS_URL, json={"title": "Goal B"}, headers=auth_headers)
    goal_b = res.json()
    client.post(
        f"{GOALS_URL}/{goal_b['id']}/tasks",
        json={"title": "Task B1", "estimated_minutes": 60, "difficulty": 3},
        headers=auth_headers,
    )

    # Generate plan
    res = client.post(f"{PLANS_URL}/generate", json=WINDOW_PAYLOAD, headers=auth_headers)
    assert res.status_code == 201

    risk = res.json()["risk_summary"]
    # Should track context switching (may be 0 or 1 depending on ordering)
    assert "context_switching_count" in risk
    assert isinstance(risk["context_switching_count"], int)
