import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan, PlanItem
from app.models.user_features import UserFeatures
from app.models.work_log import WorkLog
from app.models.task import Task


def compute_user_features(db: Session, user_id: uuid.UUID) -> dict:
    """Compute behavioral features from work log history.
    Returns dict suitable for upserting into UserFeatures.
    """
    all_logs = db.scalars(select(WorkLog).where(WorkLog.user_id == user_id)).all()
    total_count = len(all_logs)
    completed_logs = [l for l in all_logs if l.completed and l.ended_at is not None]
    completed_count = len(completed_logs)

    ratios = []
    for log in completed_logs:
        task = db.get(Task, log.task_id)
        if task is None or task.estimated_minutes is None or task.estimated_minutes <= 0:
            continue
        actual_mins = (log.ended_at - log.started_at).total_seconds() / 60
        if actual_mins <= 0:
            continue
        ratios.append(actual_mins / task.estimated_minutes)
    bias = min(sum(ratios) / len(ratios), 5.0) if ratios else 1.0

    completion_rate = completed_count / total_count if total_count > 0 else 0.0

    if completed_logs:
        hour_counts: dict[str, int] = {}
        for log in completed_logs:
            key = str(log.started_at.hour)
            hour_counts[key] = hour_counts.get(key, 0) + 1
        focus_prob = {str(h): hour_counts.get(str(h), 0) / completed_count for h in range(24) if str(h) in hour_counts}
    else:
        focus_prob = None

    return {
        "estimation_bias_multiplier": bias,
        "completion_rate": completion_rate,
        "focus_probability_by_hour": focus_prob,
        "reschedule_rate": 0.0,
        "burnout_score": 0.0,
    }



def update_user_features(db: Session, user_id: uuid.UUID) -> UserFeatures:
    """Compute and upsert UserFeatures for a user."""
    features_data = compute_user_features(db, user_id)
    features_data["last_computed_at"] = datetime.now(timezone.utc)

    existing = db.scalars(
        select(UserFeatures).where(UserFeatures.user_id == user_id)
    ).first()

    if existing:
        for key, value in features_data.items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing

    row = UserFeatures(id=uuid.uuid4(), user_id=user_id, **features_data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_user_features(db: Session, user_id: uuid.UUID) -> UserFeatures | None:
    return db.scalars(
        select(UserFeatures).where(UserFeatures.user_id == user_id)
    ).first()


def compute_alignment_score(
    db: Session, user_id: uuid.UUID, week_start: date, week_end: date
) -> dict:
    """Compare approved plan items against work logs for the given week.

    Returns a dict with:
      plan_items    — count of scheduled items in approved plans this week
      logged_tasks  — count of those tasks that have at least one work log
      alignment_score — logged_tasks / max(plan_items, 1), capped at 1.0
      week_start, week_end — echo back the window
    """
    plan_items = db.scalars(
        select(PlanItem)
        .join(Plan, PlanItem.plan_id == Plan.id)
        .where(
            PlanItem.scheduled_date >= week_start,
            PlanItem.scheduled_date <= week_end,
            Plan.scope_id == user_id,
            Plan.status == "approved",
        )
    ).all()
    plan_task_ids = {item.task_id for item in plan_items}

    window_start_dt = datetime(week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc)
    window_end_dt = datetime(week_end.year, week_end.month, week_end.day, tzinfo=timezone.utc) + timedelta(days=1)

    work_logs = db.scalars(
        select(WorkLog).where(
            WorkLog.user_id == user_id,
            WorkLog.started_at >= window_start_dt,
            WorkLog.started_at < window_end_dt,
        )
    ).all()
    worklog_task_ids = {log.task_id for log in work_logs}

    logged_tasks = len(plan_task_ids & worklog_task_ids)
    alignment_score = min(logged_tasks / max(len(plan_task_ids), 1), 1.0)
    return {
        "plan_items": len(plan_task_ids),
        "logged_tasks": logged_tasks,
        "alignment_score": alignment_score,
        "week_start": week_start,
        "week_end": week_end,
    }
