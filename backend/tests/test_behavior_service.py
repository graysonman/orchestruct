"""Unit tests for behavior_service — drives service functions directly via db fixture."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.models.base import ScopeType
from app.models.task import Task
from app.models.user_features import UserFeatures
from app.models.work_log import WorkLog
from app.models.user import User
from app.services import behavior_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@test.com",
        hashed_password="x",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _make_goal(db: Session, user_id: uuid.UUID) -> Goal:
    goal = Goal(
        id=uuid.uuid4(),
        scope_type=ScopeType.USER,
        scope_id=user_id,
        title="Test Goal",
        priority_weight=1.0,
        is_active=True,
    )
    db.add(goal)
    db.flush()
    return goal


def _make_task(db: Session, goal_id: uuid.UUID, estimated_minutes: int) -> Task:
    task = Task(
        id=uuid.uuid4(),
        goal_id=goal_id,
        title="Test Task",
        estimated_minutes=estimated_minutes,
        difficulty=2,
        dislike_score=0,
        status="pending",
    )
    db.add(task)
    db.flush()
    return task


def _make_log(
    db: Session,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    started_at: datetime,
    ended_at: datetime | None,
    completed: bool,
) -> WorkLog:
    log = WorkLog(
        id=uuid.uuid4(),
        user_id=user_id,
        task_id=task_id,
        started_at=started_at,
        ended_at=ended_at,
        completed=completed,
    )
    db.add(log)
    db.flush()
    return log


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_compute_features_no_logs(db: Session):
    user = _make_user(db)
    result = behavior_service.compute_user_features(db, user.id)
    assert result["completion_rate"] == 0.0
    assert result["estimation_bias_multiplier"] == 1.0


def test_completion_rate(db: Session):
    user = _make_user(db)
    goal = _make_goal(db, user.id)
    task = _make_task(db, goal.id, 60)

    base = datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc)
    _make_log(db, user.id, task.id, base, base + timedelta(hours=1), completed=True)
    _make_log(db, user.id, task.id, base + timedelta(hours=2), base + timedelta(hours=3), completed=True)
    _make_log(db, user.id, task.id, base + timedelta(hours=4), base + timedelta(hours=5), completed=False)
    db.commit()

    result = behavior_service.compute_user_features(db, user.id)
    assert abs(result["completion_rate"] - 2 / 3) < 0.001


def test_estimation_bias_accurate(db: Session):
    user = _make_user(db)
    goal = _make_goal(db, user.id)
    task = _make_task(db, goal.id, 60)

    base = datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc)
    _make_log(db, user.id, task.id, base, base + timedelta(minutes=60), completed=True)
    db.commit()

    result = behavior_service.compute_user_features(db, user.id)
    assert abs(result["estimation_bias_multiplier"] - 1.0) < 0.01


def test_estimation_bias_slow_user(db: Session):
    user = _make_user(db)
    goal = _make_goal(db, user.id)
    task = _make_task(db, goal.id, 60)

    base = datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc)
    _make_log(db, user.id, task.id, base, base + timedelta(minutes=90), completed=True)
    db.commit()

    result = behavior_service.compute_user_features(db, user.id)
    assert abs(result["estimation_bias_multiplier"] - 1.5) < 0.01


def test_update_user_features_upsert(db: Session):
    user = _make_user(db)
    db.commit()

    first = behavior_service.update_user_features(db, user.id)
    second = behavior_service.update_user_features(db, user.id)

    assert first.id == second.id  # Same row, no duplicates


def test_focus_probability_by_hour_structure(db: Session):
    user = _make_user(db)
    goal = _make_goal(db, user.id)
    task = _make_task(db, goal.id, 30)

    base = datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc)
    _make_log(db, user.id, task.id, base, base + timedelta(minutes=30), completed=True)
    db.commit()

    result = behavior_service.compute_user_features(db, user.id)
    prob = result["focus_probability_by_hour"]

    assert prob is not None
    # All keys must be digit strings in range 0-23
    for k in prob.keys():
        assert k.isdigit()
        assert 0 <= int(k) <= 23
    # Probabilities should sum to ~1.0
    assert abs(sum(prob.values()) - 1.0) < 0.01
