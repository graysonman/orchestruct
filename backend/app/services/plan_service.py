"""Plan generation service integrating tasks with calendar availability."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import ScopeType
from app.models.goal import Goal
from app.models.plan import Plan, PlanItem
from app.models.task import Task
from app.services import availability_service, scheduler
from app.services.scheduler import ScheduledTask


def generate_plan(
    db: Session,
    scope_type: ScopeType,
    scope_id: uuid.UUID,
    window_start: date,
    window_end: date,
) -> Plan:
    """Generate a plan for a user/team/org within a date range.

    Integrates with the calendar system to respect:
    - User's configured work hours
    - Blocked calendar events
    - Personal events
    """
    # Get all active goals for this scope
    goals = list(db.scalars(
        select(Goal).where(
            Goal.scope_type == scope_type,
            Goal.scope_id == scope_id,
            Goal.is_active == True,
        )
    ))

    # Collect pending tasks from all goals
    scheduled_tasks = []
    for goal in goals:
        tasks = list(db.scalars(
            select(Task).where(
                Task.goal_id == goal.id,
                Task.status == "pending",
            )
        ))
        for task in tasks:
            scheduled_tasks.append(ScheduledTask(
                task_id=str(task.id),
                title=task.title,
                estimated_minutes=task.estimated_minutes,
                difficulty=task.difficulty or 1,
                dislike_score=task.dislike_score,
                due_date=task.due_date,
                priority_weight=goal.priority_weight,
            ))

    # Build availability grid from calendar
    # For USER scope, we use the scope_id as user_id
    availability = None
    if scope_type == ScopeType.USER:
        availability = availability_service.build_availability_grid(
            db, scope_id, window_start, window_end
        )

    # Run scheduler with availability
    items, risk_summary = scheduler.run(
        scheduled_tasks,
        window_start,
        window_end,
        availability=availability,
    )

    # Create plan record
    plan = Plan(
        id=uuid.uuid4(),
        scope_type=scope_type,
        scope_id=scope_id,
        planning_window_start=window_start,
        planning_window_end=window_end,
        status="proposed",
        risk_summary=risk_summary,
    )
    db.add(plan)

    # Create plan items
    for item in items:
        planned_item = PlanItem(
            id=uuid.uuid4(),
            plan_id=plan.id,
            task_id=uuid.UUID(item.task_id),
            start_time=item.start_time,
            end_time=item.end_time,
            scheduled_date=item.scheduled_date,
            risk_score=item.risk_score,
            rationale=item.rationale,
        )
        db.add(planned_item)

    db.commit()
    _ = plan.items  # Lazy load before session closes

    return plan


def get_plan(db: Session, plan_id: uuid.UUID) -> Plan | None:
    """Get a plan by ID."""
    return db.get(Plan, plan_id)


def approve_plan(db: Session, plan: Plan) -> Plan:
    """Approve a proposed plan."""
    plan.status = "approved"
    db.commit()
    db.refresh(plan)
    return plan


def reject_plan(db: Session, plan: Plan) -> Plan:
    """Reject/invalidate a plan."""
    plan.status = "invalidated"
    db.commit()
    db.refresh(plan)
    return plan
