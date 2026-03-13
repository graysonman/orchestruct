import uuid
from datetime import datetime
from pydantic import BaseModel


class WorkLogCreate(BaseModel):
    task_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None = None
    completed: bool = False
    notes: str | None = None


class WorkLogUpdate(BaseModel):
    ended_at: datetime | None = None
    completed: bool | None = None
    notes: str | None = None


class WorkLogResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    completed: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
