import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.deps import CurrentUser
from app.db.session import DBSession
from app.models.task import Task
from app.models.goal import Goal
from app.models.base import ScopeType
from app.models.work_log import WorkLog
from app.schemas.worklogs import WorkLogCreate, WorkLogResponse, WorkLogUpdate
from app.services import behavior_service

router = APIRouter(prefix="/worklogs", tags=["worklogs"])


def _as_utc(value: datetime) -> datetime:
    """Make a timestamp comparable regardless of where it came from.

    The column is `DateTime(timezone=True)`, but not every backend preserves
    that — SQLite hands back offset-naive values, while a timestamp parsed from
    a request body is offset-aware. Comparing the two raises TypeError, so a
    naive value is read as UTC, which is how it was stored. Same normalization
    as routers/metrics.py applies to `last_computed_at`.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _get_owned_worklog(worklog_id: uuid.UUID, db: DBSession, current_user: CurrentUser) -> WorkLog:
    log = db.scalars(
        select(WorkLog)
        .where(WorkLog.id == worklog_id)
        .options(joinedload(WorkLog.task))
    ).first()
    if not log or log.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="WorkLog not found")
    return log


@router.post("", response_model=WorkLogResponse, status_code=status.HTTP_201_CREATED)
def create_worklog(payload: WorkLogCreate, db: DBSession, current_user: CurrentUser):
    """Record time spent on a task, then refresh the user's behavioral features.

    The recompute is what closes the learning loop: comparing logged duration
    against the task's estimate updates `estimation_bias_multiplier`, which
    plan_service reads on the next generation to pad or trim estimates. Without
    it, logging work would change nothing until `GET /metrics/me` happened to
    run and find the features more than a day stale.
    """
    # Reject a log against someone else's task rather than silently attributing
    # a stranger's estimate to this user's bias. Tasks are reachable only under
    # their goal, and goals carry the scope, so ownership is checked through
    # the join.
    task = db.get(Task, payload.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    goal = db.get(Goal, task.goal_id)
    if goal is None or (
        goal.scope_type == ScopeType.USER and goal.scope_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail="Task not found")

    if payload.ended_at is not None and _as_utc(payload.ended_at) <= _as_utc(
        payload.started_at
    ):
        raise HTTPException(
            status_code=422, detail={"errors": ["ended_at must be after started_at"]}
        )

    log = WorkLog(
        id=uuid.uuid4(),
        user_id=current_user.id,
        task_id=payload.task_id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        completed=payload.completed,
        notes=payload.notes,
    )
    db.add(log)
    db.commit()

    behavior_service.update_user_features(db, current_user.id)

    return _get_owned_worklog(log.id, db, current_user)


@router.get("", response_model=list[WorkLogResponse])
def list_worklogs(db: DBSession, current_user: CurrentUser):
    """Newest first — a history is read from the most recent entry backwards."""
    return list(
        db.scalars(
            select(WorkLog)
            .where(WorkLog.user_id == current_user.id)
            # Every row's task is read to render its title. Without this the
            # response costs one query per log.
            .options(joinedload(WorkLog.task))
            .order_by(WorkLog.started_at.desc())
        )
    )


@router.get("/{worklog_id}", response_model=WorkLogResponse)
def get_worklog(worklog_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    return _get_owned_worklog(worklog_id, db, current_user)


@router.patch("/{worklog_id}", response_model=WorkLogResponse)
def update_worklog(
    worklog_id: uuid.UUID,
    payload: WorkLogUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Amend a log — in practice, closing one that was started without an end.

    Starting a log and stopping it later is the only way to time work as it
    happens; a log with no `ended_at` is invisible to the learning loop until
    this endpoint gives it one.

    `exclude_unset` is what makes a partial update possible: an omitted key is
    left alone, while an explicit null clears the column. Sending
    `{"ended_at": null}` reopens a log rather than being ignored.
    """
    log = _get_owned_worklog(worklog_id, db, current_user)

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(log, field, value)

    if log.ended_at is not None and _as_utc(log.ended_at) <= _as_utc(log.started_at):
        raise HTTPException(
            status_code=422, detail={"errors": ["ended_at must be after started_at"]}
        )

    db.commit()

    # Same reason as create: the duration this log now reports is what moves
    # estimation_bias_multiplier, and the next plan reads it.
    behavior_service.update_user_features(db, current_user.id)

    return _get_owned_worklog(worklog_id, db, current_user)
