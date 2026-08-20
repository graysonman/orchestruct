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


def test_response_embeds_the_task(client: TestClient, auth_headers, created_log, created_task):
    """A history is unreadable without titles, and there is no endpoint the
    client could use to look one up — tasks are only reachable under a goal."""
    assert created_log["task"]["title"] == created_task["title"]
    assert created_log["task"]["estimated_minutes"] == TASK_PAYLOAD["estimated_minutes"]


def test_list_is_newest_first(client: TestClient, auth_headers, created_task):
    for started in ("2026-03-11T09:00:00+00:00", "2026-03-13T09:00:00+00:00"):
        client.post(
            WORKLOGS_URL,
            json={"task_id": created_task["id"], "started_at": started, "completed": False},
            headers=auth_headers,
        )
    starts = [log["started_at"] for log in client.get(WORKLOGS_URL, headers=auth_headers).json()]
    assert starts == sorted(starts, reverse=True)


def test_create_refreshes_user_features(client: TestClient, auth_headers, created_task, db):
    """The learning loop: a log whose duration overshoots the estimate must move
    estimation_bias_multiplier, which plan generation reads on its next run.

    Before this, features were only recomputed by GET /metrics/me, and only when
    they were already more than a day stale — so logging work changed nothing.

    Asserted against the table rather than through /metrics/me on purpose: that
    endpoint recomputes when features are missing, so it would report the right
    number whether or not the write path did anything.
    """
    from app.models.user_features import UserFeatures

    assert db.query(UserFeatures).count() == 0

    # 120 minutes logged against a 60-minute estimate → bias of 2.0.
    res = client.post(
        WORKLOGS_URL,
        json={
            "task_id": created_task["id"],
            "started_at": "2026-03-13T09:00:00+00:00",
            "ended_at": "2026-03-13T11:00:00+00:00",
            "completed": True,
        },
        headers=auth_headers,
    )
    assert res.status_code == 201

    features = db.query(UserFeatures).one()
    assert features.estimation_bias_multiplier == pytest.approx(2.0)


def test_incomplete_log_does_not_move_the_bias(
    client: TestClient, auth_headers, created_task, db
):
    """Only finished work carries a duration worth learning from — an open log
    has no end time, and an abandoned one says nothing about estimation."""
    from app.models.user_features import UserFeatures

    client.post(
        WORKLOGS_URL,
        json={
            "task_id": created_task["id"],
            "started_at": "2026-03-13T09:00:00+00:00",
            "completed": False,
        },
        headers=auth_headers,
    )

    features = db.query(UserFeatures).one()
    assert features.estimation_bias_multiplier == pytest.approx(1.0)
    assert features.completion_rate == pytest.approx(0.0)


def test_rejects_a_log_against_someone_elses_task(
    client: TestClient, auth_headers_b, created_task
):
    """Otherwise a stranger's estimate would pollute this user's bias."""
    res = client.post(
        WORKLOGS_URL,
        json={
            "task_id": created_task["id"],
            "started_at": "2026-03-13T09:00:00+00:00",
            "completed": False,
        },
        headers=auth_headers_b,
    )
    assert res.status_code == 404


def test_rejects_an_end_before_the_start(client: TestClient, auth_headers, created_task):
    res = client.post(
        WORKLOGS_URL,
        json={
            "task_id": created_task["id"],
            "started_at": "2026-03-13T11:00:00+00:00",
            "ended_at": "2026-03-13T09:00:00+00:00",
            "completed": True,
        },
        headers=auth_headers,
    )
    assert res.status_code == 422
    assert "errors" in res.json()["detail"]


@pytest.fixture
def open_log(client: TestClient, auth_headers, created_task):
    """A log that was started but never ended — invisible to the loop until closed."""
    res = client.post(
        WORKLOGS_URL,
        json={
            "task_id": created_task["id"],
            "started_at": "2026-03-13T09:00:00+00:00",
            "completed": False,
        },
        headers=auth_headers,
    )
    return res.json()


def test_patch_closes_an_open_log(client: TestClient, auth_headers, open_log):
    res = client.patch(
        f"{WORKLOGS_URL}/{open_log['id']}",
        json={"ended_at": "2026-03-13T10:00:00+00:00", "completed": True},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["completed"] is True
    assert res.json()["ended_at"] is not None


def test_patch_leaves_omitted_fields_alone(client: TestClient, auth_headers, open_log):
    """exclude_unset: sending only `completed` must not wipe the notes."""
    client.patch(
        f"{WORKLOGS_URL}/{open_log['id']}",
        json={"notes": "started before standup"},
        headers=auth_headers,
    )
    res = client.patch(
        f"{WORKLOGS_URL}/{open_log['id']}",
        json={"ended_at": "2026-03-13T10:00:00+00:00", "completed": True},
        headers=auth_headers,
    )
    assert res.json()["notes"] == "started before standup"


def test_patch_refreshes_user_features(client: TestClient, auth_headers, open_log, db):
    """Closing a log is what makes it count — the bias must move on the PATCH."""
    from app.models.user_features import UserFeatures

    # An open log contributes nothing, so the bias sits at its default.
    assert db.query(UserFeatures).one().estimation_bias_multiplier == pytest.approx(1.0)

    # 120 minutes against a 60-minute estimate → 2.0.
    client.patch(
        f"{WORKLOGS_URL}/{open_log['id']}",
        json={"ended_at": "2026-03-13T11:00:00+00:00", "completed": True},
        headers=auth_headers,
    )

    db.expire_all()
    assert db.query(UserFeatures).one().estimation_bias_multiplier == pytest.approx(2.0)


def test_patch_rejects_an_end_before_the_start(client: TestClient, auth_headers, open_log):
    res = client.patch(
        f"{WORKLOGS_URL}/{open_log['id']}",
        json={"ended_at": "2026-03-13T08:00:00+00:00"},
        headers=auth_headers,
    )
    assert res.status_code == 422
    assert "errors" in res.json()["detail"]


def test_patch_ownership_isolation(client: TestClient, auth_headers_b, open_log):
    res = client.patch(
        f"{WORKLOGS_URL}/{open_log['id']}",
        json={"completed": True},
        headers=auth_headers_b,
    )
    assert res.status_code == 404
