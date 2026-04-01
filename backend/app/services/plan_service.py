"""Plan generation service integrating tasks with calendar availability."""

import uuid
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import ScopeType
from app.models.goal import Goal
from app.models.plan import Plan, PlanItem
from app.models.task import Task
from app.models.user import User
from app.services import availability_service, behavior_service, google_calendar_service, scheduler, team_service
from app.services.scheduler import MemberAvailability, ScheduledTask


def generate_plan(
    db: Session,
    scope_type: ScopeType,
    scope_id: uuid.UUID,
    window_start: date,
    window_end: date,
) -> Plan:
    """Generate a plan for a user/team/org within a date range."""
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
                goal_id=str(goal.id),
            ))

    if scope_type == ScopeType.USER:
        # Auto-sync Google Calendar before building availability grid
        google_conflicts = []
        user = db.get(User, scope_id)
        if user and user.google_access_token:
            try:
                access_token = google_calendar_service.ensure_fresh_token(db, user)
                time_min = datetime.combine(window_start, time.min)
                time_max = datetime.combine(window_end, time.max)
                google_events = google_calendar_service.fetch_google_events(
                    access_token, time_min, time_max
                )
                google_calendar_service.sync_google_to_local(db, scope_id, google_events)
                google_conflicts = google_calendar_service.detect_conflicts(
                    db, scope_id, google_events
                )
            except Exception:
                pass  # Google sync failure is non-fatal — plan with local data

        estimation_bias_multiplier = 1.0
        features = behavior_service.get_user_features(db, scope_id)
        if features:
            estimation_bias_multiplier = features.estimation_bias_multiplier

        availability = availability_service.build_availability_grid(
            db, scope_id, window_start, window_end
        )
        items, risk_summary = scheduler.run(
            scheduled_tasks,
            window_start,
            window_end,
            availability=availability,
            estimation_bias_multiplier=estimation_bias_multiplier,
        )
        risk_summary["google_conflicts"] = google_conflicts

    elif scope_type == ScopeType.TEAM:
        # Team path: build per-member availability grids and assign tasks across members
        # TODO Stage 7: extend alignment score for team scope
        members_db = team_service.list_members(db, scope_id)
        member_availabilities = []
        for m in members_db:
            avail = availability_service.build_availability_grid(
                db, m.user_id, window_start, window_end
            )
            features = behavior_service.get_user_features(db, m.user_id)
            bias = features.estimation_bias_multiplier if features else 1.0
            member_availabilities.append(MemberAvailability(m.user_id, avail, bias))

        items, risk_summary = scheduler.assign_tasks_to_members(
            scheduled_tasks, window_start, window_end, member_availabilities
        )

    else:
        items, risk_summary = [], {}

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

    # Create plan items — assigned_to_user_id is set for team plans
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
            assigned_to_user_id=item.assigned_to_user_id,
        )
        db.add(planned_item)

    db.commit()
    _ = plan.items  # Lazy load before session closes

    return plan


def get_plan(db: Session, plan_id: uuid.UUID) -> Plan | None:
    """Get a plan by ID."""
    return db.get(Plan, plan_id)


def approve_plan(db: Session, plan: Plan) -> Plan:
    """Approve a proposed plan and push blocks to Google Calendar if connected."""
    plan.status = "approved"
    db.commit()
    db.refresh(plan)

    # Push to Google Calendar for user-scoped plans only
    if plan.scope_type == ScopeType.USER:
        user = db.get(User, plan.scope_id)
        if user and user.google_access_token:
            try:
                google_calendar_service.ensure_fresh_token(db, user)
                google_calendar_service.push_plan_to_google(db, plan, user)
            except Exception:
                pass  # Google push failure is non-fatal — plan is still approved

    return plan


def reject_plan(db: Session, plan: Plan) -> Plan:
    """Reject/invalidate a plan."""
    plan.status = "invalidated"
    db.commit()
    db.refresh(plan)
    return plan
