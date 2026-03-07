import uuid
from datetime import date, time, datetime

from pydantic import BaseModel

from app.models.base import ScopeType

class PlanGenerate(BaseModel):
    planning_window_start: date
    planning_window_end: date

class PlanItemResponse(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    task_id: uuid.UUID
    scheduled_date: date
    start_time: time
    end_time: time
    risk_score: float | None
    rationale: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}

class PlanResponse(BaseModel):
    id: uuid.UUID
    scope_type: ScopeType
    scope_id: uuid.UUID
    planning_window_start: date
    planning_window_end: date
    status: str
    risk_summary: dict | None
    items: list[PlanItemResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}