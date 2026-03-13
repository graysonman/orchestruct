import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

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

    # estimation_bias_multiplier
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

    # completion_rate
    completion_rate = completed_count / total_count if total_count > 0 else 0.0

    # focus_probability_by_hour
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
