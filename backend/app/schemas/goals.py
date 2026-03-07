import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.base import ScopeType


class GoalCreate(BaseModel):
    title: str
    description: str | None = None
    scope_type: ScopeType = ScopeType.USER
    scope_id: uuid.UUID | None = None
    success_metric_type: str | None = None
    target_value: float | None = None
    target_date: date | None = None
    priority_weight: float = 1.0
    min_weekly_hours: float | None = None
    max_weekly_hours: float | None = None
    constraints: dict | None = None


class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    success_metric_type: str | None = None
    target_value: float | None = None
    target_date: date | None = None
    priority_weight: float | None = None
    min_weekly_hours: float | None = None
    max_weekly_hours: float | None = None
    constraints: dict | None = None
    is_active: bool | None = None


class GoalResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    scope_type: ScopeType
    scope_id: uuid.UUID
    success_metric_type: str | None
    target_value: float | None
    target_date: date | None
    priority_weight: float
    min_weekly_hours: float | None
    max_weekly_hours: float | None
    constraints: dict | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    estimated_minutes: int | None = None
    difficulty: int | None = None
    due_date: date | None = None
    dislike_score: int = 0
    owner_user_id: uuid.UUID | None = None
    prerequisites: list | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    estimated_minutes: int | None = None
    difficulty: int | None = None
    due_date: date | None = None
    dislike_score: int | None = None
    owner_user_id: uuid.UUID | None = None
    prerequisites: list | None = None
    status: str | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    title: str
    description: str | None
    estimated_minutes: int | None
    difficulty: int | None
    due_date: date | None
    dislike_score: int
    owner_user_id: uuid.UUID | None
    prerequisites: list | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
