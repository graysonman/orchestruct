import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.models.nudge import Nudge
from app.models.plan import Plan, PlanItem
from app.models.user_features import UserFeatures
from app.models.work_log import WorkLog

REGISTER_URL = "/api/v1/auth/register"
GOALS_URL = "/api/v1/goals"
NUDGES_URL = "/api/v1/nudges"
ALIGNMENT_URL = "/api/v1/metrics/alignment"

USER_A = {"email": "nudge_a@example.com", "password": "secret123"}
USER_B = {"email": "nudge_b@example.com", "password": "secret123"}


@pytest.fixture
def auth_headers(client: TestClient):
    res = client.post(REGISTER_URL, json=USER_A)
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def auth_headers_b(client: TestClient):
    res = client.post(REGISTER_URL, json=USER_B)
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def user_a_id(client: TestClient, auth_headers):
    res = client.get("/api/v1/auth/me", headers=auth_headers)
    return res.json()["id"]


@pytest.fixture
def user_b_id(client: TestClient, auth_headers_b):
    res = client.get("/api/v1/auth/me", headers=auth_headers_b)
    return res.json()["id"]


# ── helpers ──────────────────────────────────────────────────────────────────

def seed_features(db, user_id: str, **kwargs):
    defaults = {
        "completion_rate": 0.8,
        "estimation_bias_multiplier": 1.0,
        "burnout_score": 0.0,
        "reschedule_rate": 0.0,
        "focus_probability_by_hour": None,
        "last_computed_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    row = UserFeatures(id=uuid.uuid4(), user_id=uuid.UUID(user_id), **defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ── tests ─────────────────────────────────────────────────────────────────────

def test_evaluate_no_features_returns_empty(client: TestClient, auth_headers):
    """New user with no features → no nudges triggered."""
    res = client.post(f"{NUDGES_URL}/evaluate", headers=auth_headers)
    assert res.status_code == 201
    assert res.json() == []


def test_evaluate_burnout_creates_nudge(client: TestClient, db, auth_headers, user_a_id):
    """Seeding burnout_score=0.8 → burnout_risk nudge is created."""
    seed_features(db, user_a_id, burnout_score=0.8)
    res = client.post(f"{NUDGES_URL}/evaluate", headers=auth_headers)
    assert res.status_code == 201
    nudges = res.json()
    types = [n["nudge_type"] for n in nudges]
    assert "burnout_risk" in types

    # verify fields present
    burnout_nudge = next(n for n in nudges if n["nudge_type"] == "burnout_risk")
    assert burnout_nudge["status"] == "pending"
    assert burnout_nudge["trigger_data"]["burnout_score"] == pytest.approx(0.8)


def test_evaluate_deduplication(client: TestClient, db, auth_headers, user_a_id):
    """Calling evaluate twice does not create a second pending nudge of the same type."""
    seed_features(db, user_a_id, burnout_score=0.8)

    res1 = client.post(f"{NUDGES_URL}/evaluate", headers=auth_headers)
    res2 = client.post(f"{NUDGES_URL}/evaluate", headers=auth_headers)
    assert res1.status_code == 201
    assert res2.status_code == 201
    # second call should return empty (already pending)
    assert res2.json() == []

    # only one pending nudge in the DB
    list_res = client.get(f"{NUDGES_URL}?status=pending", headers=auth_headers)
    burnout_nudges = [n for n in list_res.json() if n["nudge_type"] == "burnout_risk"]
    assert len(burnout_nudges) == 1


def test_list_nudges(client: TestClient, db, auth_headers, user_a_id):
    """After evaluate, GET /nudges returns the created nudge."""
    seed_features(db, user_a_id, burnout_score=0.9)
    client.post(f"{NUDGES_URL}/evaluate", headers=auth_headers)

    res = client.get(NUDGES_URL, headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_acknowledge_nudge(client: TestClient, db, auth_headers, user_a_id):
    """Acknowledging a nudge sets status=acknowledged and acknowledged_at."""
    seed_features(db, user_a_id, burnout_score=0.9)
    nudges = client.post(f"{NUDGES_URL}/evaluate", headers=auth_headers).json()
    nudge_id = nudges[0]["id"]

    res = client.post(f"{NUDGES_URL}/{nudge_id}/acknowledge", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "acknowledged"
    assert body["acknowledged_at"] is not None


def test_dismiss_nudge(client: TestClient, db, auth_headers, user_a_id):
    """Dismissing a nudge sets status=dismissed."""
    seed_features(db, user_a_id, burnout_score=0.9)
    nudges = client.post(f"{NUDGES_URL}/evaluate", headers=auth_headers).json()
    nudge_id = nudges[0]["id"]

    res = client.post(f"{NUDGES_URL}/{nudge_id}/dismiss", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "dismissed"


def test_nudge_ownership_isolation(client: TestClient, db, auth_headers, auth_headers_b, user_a_id):
    """User B cannot access user A's nudge — gets 404."""
    seed_features(db, user_a_id, burnout_score=0.9)
    nudges = client.post(f"{NUDGES_URL}/evaluate", headers=auth_headers).json()
    nudge_id = nudges[0]["id"]

    res = client.get(f"{NUDGES_URL}/{nudge_id}", headers=auth_headers_b)
    assert res.status_code == 404


def test_alignment_score_endpoint(client: TestClient, db, auth_headers, user_a_id):
    """Seeding an approved plan + worklog in the same week → alignment_score > 0."""
    uid = uuid.UUID(user_a_id)

    # create a goal + task via API
    goal_res = client.post(GOALS_URL, json={"title": "Alignment Goal"}, headers=auth_headers)
    goal_id = goal_res.json()["id"]
    task_res = client.post(
        f"{GOALS_URL}/{goal_id}/tasks",
        json={"title": "Alignment Task", "estimated_minutes": 30, "difficulty": 1},
        headers=auth_headers,
    )
    task_id = uuid.UUID(task_res.json()["id"])

    week_start = date(2026, 3, 9)
    week_end = date(2026, 3, 15)

    # seed an approved plan with a plan item for that task in the window
    from app.models.base import ScopeType
    plan = Plan(
        id=uuid.uuid4(),
        scope_type=ScopeType.USER,
        scope_id=uid,
        planning_window_start=week_start,
        planning_window_end=week_end,
        status="approved",
    )
    db.add(plan)
    db.flush()

    item = PlanItem(
        id=uuid.uuid4(),
        plan_id=plan.id,
        task_id=task_id,
        scheduled_date=date(2026, 3, 10),
        start_time=__import__("datetime").time(9, 0),
        end_time=__import__("datetime").time(9, 30),
    )
    db.add(item)

    # seed a worklog for the same task in the same window
    log = WorkLog(
        id=uuid.uuid4(),
        user_id=uid,
        task_id=task_id,
        started_at=datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 3, 10, 9, 30, tzinfo=timezone.utc),
        completed=True,
    )
    db.add(log)
    db.commit()

    res = client.get(
        ALIGNMENT_URL,
        params={"week_start": "2026-03-09", "week_end": "2026-03-15"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["plan_items"] == 1
    assert body["logged_tasks"] == 1
    assert body["alignment_score"] == pytest.approx(1.0)
