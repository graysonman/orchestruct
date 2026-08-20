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


def test_reading_does_not_recompute(client: TestClient, auth_headers, db):
    """Reads are pure once the row exists.

    The worklog endpoints refresh features on every write, so there is no stale
    window for this endpoint to close — and recomputing here would make a GET
    write to the database on every dashboard load.
    """
    from app.models.user_features import UserFeatures

    client.get(METRICS_URL, headers=auth_headers)
    first = db.query(UserFeatures).one().last_computed_at

    for _ in range(3):
        client.get(METRICS_URL, headers=auth_headers)

    db.expire_all()
    assert db.query(UserFeatures).one().last_computed_at == first


def test_reflects_a_worklog_immediately(client: TestClient, auth_headers, db):
    """The write path is what keeps this endpoint current — a log submitted a
    second ago must show up, with no staleness threshold standing in the way."""
    goal = client.post(
        "/api/v1/goals", json={"title": "Metrics goal"}, headers=auth_headers
    ).json()
    task = client.post(
        f"/api/v1/goals/{goal['id']}/tasks",
        json={"title": "Metrics task", "estimated_minutes": 60},
        headers=auth_headers,
    ).json()

    # Establish a features row first, so any refresh must come from the write.
    assert client.get(METRICS_URL, headers=auth_headers).json()[
        "estimation_bias_multiplier"
    ] == pytest.approx(1.0)

    client.post(
        "/api/v1/worklogs",
        json={
            "task_id": task["id"],
            "started_at": "2026-03-13T09:00:00+00:00",
            "ended_at": "2026-03-13T10:30:00+00:00",
            "completed": True,
        },
        headers=auth_headers,
    )

    res = client.get(METRICS_URL, headers=auth_headers)
    assert res.json()["estimation_bias_multiplier"] == pytest.approx(1.5)


def test_stale_features_are_returned_as_stored(client: TestClient, auth_headers, db):
    """No staleness threshold: an old row is served, not silently recomputed.

    Previously this endpoint recomputed whenever `last_computed_at` was more
    than a day old. That is now the worklog endpoints' job, and re-deriving
    here would hide a stale write path rather than expose it.
    """
    from datetime import datetime, timedelta, timezone

    from app.models.user_features import UserFeatures

    client.get(METRICS_URL, headers=auth_headers)

    # Backdate the row past the old threshold and plant a value that no work
    # log could produce, so a recompute would visibly overwrite it.
    row = db.query(UserFeatures).one()
    row.estimation_bias_multiplier = 3.7
    row.last_computed_at = datetime.now(timezone.utc) - timedelta(days=2)
    db.commit()

    res = client.get(METRICS_URL, headers=auth_headers)
    assert res.json()["estimation_bias_multiplier"] == pytest.approx(3.7)
