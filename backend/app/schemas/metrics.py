import uuid
from datetime import date, datetime
from pydantic import BaseModel


class UserFeaturesResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    completion_rate: float
    estimation_bias_multiplier: float
    focus_probability_by_hour: dict | None
    reschedule_rate: float
    burnout_score: float
    last_computed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlignmentScoreResponse(BaseModel):
    plan_items: int
    logged_tasks: int
    alignment_score: float
    week_start: date
    week_end: date
