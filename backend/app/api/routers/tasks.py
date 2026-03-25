import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.api.routers.goals import can_access_scoped_record
from app.db.session import DBSession
from app.schemas.goals import TaskCreate, TaskResponse, TaskUpdate
from app.services import goal_service, task_service

router = APIRouter(prefix="/goals/{goal_id}/tasks", tags=["tasks"])


def _get_owned_goal(goal_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    """Fetch a goal and verify access. Raises 404 if missing or inaccessible."""
    goal = goal_service.get_goal(db, goal_id)
    if not goal or not can_access_scoped_record(db, goal, current_user):
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(goal_id: uuid.UUID, payload: TaskCreate, db: DBSession, current_user: CurrentUser):
    _get_owned_goal(goal_id, db, current_user)
    task = task_service.create_task(
        db,
        goal_id,
        title=payload.title,
        description=payload.description,
        estimated_minutes=payload.estimated_minutes,
        difficulty=payload.difficulty,
        due_date=payload.due_date,
        dislike_score=payload.dislike_score,
        owner_user_id=payload.owner_user_id, 
        prerequisites=payload.prerequisites,
    )
    return task

@router.get("", response_model=list[TaskResponse])
def list_task(goal_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    _get_owned_goal(goal_id, db, current_user)
    return task_service.list_tasks(db, goal_id=goal_id)

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: uuid.UUID, goal_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    _get_owned_goal(goal_id, db, current_user)
    task = task_service.get_task(db, task_id)
    if not task or task.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(task_id: uuid.UUID, goal_id: uuid.UUID, payload: TaskUpdate, db: DBSession, current_user: CurrentUser):
    _get_owned_goal(goal_id, db, current_user)
    task = task_service.get_task(db, task_id)
    if not task or task.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Task not found")
    updates = payload.model_dump(exclude_unset=True)
    return task_service.update_task(db, task, **updates)

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: uuid.UUID, goal_id: uuid.UUID, db:DBSession, current_user:CurrentUser):
    _get_owned_goal(goal_id, db, current_user)
    task = task_service.get_task(db, task_id)
    if not task or task.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Task not found")
    task_service.delete_task(db, task)