import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import ScopeType
from app.models.goal import Goal


def create_goal(db: Session, scope_type: ScopeType, scope_id: uuid.UUID, **fields) -> Goal:
    goal = Goal(id=uuid.uuid4(), scope_type=scope_type, scope_id=scope_id, **fields)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def get_goal(db: Session, goal_id: uuid.UUID) -> Goal | None:
    return db.get(Goal, goal_id)


def list_goals(db: Session, scope_type: ScopeType, scope_id: uuid.UUID) -> list[Goal]:
    return list(
        db.scalars(
            select(Goal).where(Goal.scope_type == scope_type, Goal.scope_id == scope_id)
        )
    )


def update_goal(db: Session, goal: Goal, **fields) -> Goal:
    for key, value in fields.items():
        setattr(goal, key, value)
    db.commit()
    db.refresh(goal)
    return goal


def delete_goal(db: Session, goal: Goal) -> None:
    db.delete(goal)
    db.commit()
