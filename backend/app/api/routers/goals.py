import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.db.session import DBSession
from app.models.base import ScopeType
from app.schemas.goals import GoalCreate, GoalResponse, GoalUpdate
from app.services import goal_service

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, db: DBSession, current_user: CurrentUser):
    scope_id = payload.scope_id or current_user.id
    goal = goal_service.create_goal(
        db,
        scope_type=payload.scope_type,
        scope_id=scope_id,
        title=payload.title,
        description=payload.description,
        success_metric_type=payload.success_metric_type,
        target_value=payload.target_value,
        target_date=payload.target_date,
        priority_weight=payload.priority_weight,
        min_weekly_hours=payload.min_weekly_hours,
        max_weekly_hours=payload.max_weekly_hours,
        constraints=payload.constraints,
    )
    return goal


@router.get("", response_model=list[GoalResponse])
def list_goals(db: DBSession, current_user: CurrentUser):
    return goal_service.list_goals(db, scope_type=ScopeType.USER, scope_id=current_user.id)


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(goal_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    goal = goal_service.get_goal(db, goal_id)
    if not goal or goal.scope_id != current_user.id:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(goal_id: uuid.UUID, payload: GoalUpdate, db: DBSession, current_user: CurrentUser):
    goal = goal_service.get_goal(db, goal_id)
    if not goal or goal.scope_id != current_user.id:
        raise HTTPException(status_code=404, detail="Goal not found")
    updates = payload.model_dump(exclude_unset=True)
    return goal_service.update_goal(db, goal, **updates)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    goal = goal_service.get_goal(db, goal_id)
    if not goal or goal.scope_id != current_user.id:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal_service.delete_goal(db, goal)
