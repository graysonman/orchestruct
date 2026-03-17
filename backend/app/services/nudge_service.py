import uuid
from datetime import datetime, timezone

from sqlalchemy import func as sqlfunc, select
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.models.nudge import Nudge
from app.models.plan import Plan
from app.models.task import Task
from app.models.user_features import UserFeatures


def evaluate_nudges(db: Session, user_id: uuid.UUID) -> list[Nudge]:
    """Run all nudge conditions and persist any newly triggered nudges.
    Deduplicates: will not create a second nudge of the same type if one is
    already pending for this user.
    """
    features = db.scalars(
        select(UserFeatures).where(UserFeatures.user_id == user_id)
    ).first()

    pending_task_count = db.scalar(
        select(sqlfunc.count(Task.id))
        .join(Goal, Task.goal_id == Goal.id)
        .where(Goal.scope_id == user_id, Task.status == "pending")
    ) or 0

    has_unapproved_plan = db.scalars(
        select(Plan).where(
            Plan.scope_id == user_id,
            Plan.status == "proposed",
        )
    ).first() is not None

    triggered = _evaluate_conditions(features, pending_task_count, has_unapproved_plan)

    existing_pending_types = set(
        db.scalars(
            select(Nudge.nudge_type).where(
                Nudge.user_id == user_id,
                Nudge.status == "pending",
            )
        ).all()
    )

    new_nudges: list[Nudge] = []
    for nudge_type, message, trigger_data in triggered:
        if nudge_type in existing_pending_types:
            continue
        nudge = Nudge(
            id=uuid.uuid4(),
            user_id=user_id,
            nudge_type=nudge_type,
            message=message,
            trigger_data=trigger_data,
            status="pending",
        )
        db.add(nudge)
        new_nudges.append(nudge)

    db.commit()
    for n in new_nudges:
        db.refresh(n)
    return new_nudges


def _evaluate_conditions(
    features: UserFeatures | None,
    pending_task_count: int,
    has_unapproved_plan: bool,
) -> list[tuple[str, str, dict]]:
    """Pure function: evaluate behavioral signals and return a list of
    (nudge_type, message, trigger_data) tuples for each condition that fires.

    Conditions to implement:
    - burnout_risk:         features.burnout_score > 0.6
    - low_completion:       features.completion_rate < 0.5 AND > 0 (needs data)
    - overestimation_bias:  features.estimation_bias_multiplier > 1.5
    - unscheduled_tasks:    pending_task_count > 5
    - plan_not_approved:    has_unapproved_plan is True
    """
    nudges: list[tuple[str, str, dict]] = []

    if features is not None:
        if features.burnout_score > 0.6:
            nudges.append((
                "burnout_risk",
                "Your burnout score is high. You should consider reducing your workload.",
                {"burnout_score": features.burnout_score},
            ))
        if features.completion_rate < 0.5 and features.completion_rate > 0:
            nudges.append((
                "low_completion",
                "You have too many items on your list that aren't completed. Try to focus on those and knock some out.",
                {"completion_rate": features.completion_rate},
            ))
        if features.estimation_bias_multiplier > 1.5:
            nudges.append((
                "overestimation_bias",
                "You are overestimating how much you can get done. Consider spreading out some of your work.",
                {"estimation_bias_multiplier": features.estimation_bias_multiplier},
            ))

    if pending_task_count > 5:
        nudges.append((
            "unscheduled_tasks",
            "You have a lot of tasks that have not been assigned yet. Consider assigning those tasks.",
            {"pending_task_count": pending_task_count},
        ))

    if has_unapproved_plan:
        nudges.append((
            "plan_not_approved",
            "You have a plan to approve. Consider approving the plan to get your goals on track.",
            {"has_unapproved_plan": has_unapproved_plan},
        ))

    return nudges


def get_nudges(db: Session, user_id: uuid.UUID, status: str | None = None) -> list[Nudge]:
    """List nudges for a user, optionally filtered by status."""
    stmt = select(Nudge).where(Nudge.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Nudge.status == status)
    return list(db.scalars(stmt).all())


def get_nudge(db: Session, nudge_id: uuid.UUID) -> Nudge | None:
    return db.get(Nudge, nudge_id)


def acknowledge_nudge(db: Session, nudge: Nudge) -> Nudge:
    nudge.status = "acknowledged"
    nudge.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(nudge)
    return nudge


def dismiss_nudge(db: Session, nudge: Nudge) -> Nudge:
    nudge.status = "dismissed"
    db.commit()
    db.refresh(nudge)
    return nudge
