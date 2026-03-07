import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import date

from app.models.base import ScopeType
from app.models.plan import Plan, PlanItem
from app.models.task import Task
from app.models.goal import Goal

from app.services.scheduler import ScheduledTask

from app.services import scheduler

def generate_plan(db: Session, scope_type: ScopeType, scope_id:uuid.UUID, window_start: date, window_end: date) -> Plan:
    goals = list(db.scalars(select(Goal).where(
                                Goal.scope_type == scope_type,
                                Goal.scope_id == scope_id,
                                Goal.is_active == True
                               )
                            )
                )
    
    scheduled = []
    for goal in goals:
        tasks = list(db.scalars(select(Task).where(Task.goal_id == goal.id, Task.status == "pending")))
        for task in tasks:
            scheduled.append(ScheduledTask(
                task_id=str(task.id),
                title=task.title,
                estimated_minutes=task.estimated_minutes,
                difficulty=task.difficulty or 1,
                dislike_score=task.dislike_score,
                due_date=task.due_date,
                priority_weight=goal.priority_weight
        ))
            
    items, risk_summary = scheduler.run(scheduled, window_start, window_end)

    plan = Plan(
        id=uuid.uuid4(),
        scope_type=scope_type,
        scope_id=scope_id,
        planning_window_start=window_start,
        planning_window_end=window_end,
        status="proposed",
        risk_summary=risk_summary
    )
    db.add(plan)

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
    _ = plan.items # Lazy load before session closes

    return plan

def get_plan(db: Session, plan_id: uuid.UUID) -> Plan | None:
    return db.get(Plan, plan_id)

def approve_plan(db: Session, plan: Plan) -> Plan:
    plan.status = "approved"
    db.commit()
    db.refresh(plan) 
    return plan

def reject_plan(db: Session, plan: Plan) -> Plan:
    plan.status = "invalidated"
    db.commit()
    db.refresh(plan) 
    return plan