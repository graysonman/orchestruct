import uuid
from datetime import datetime

from pydantic import BaseModel


class MeetingUploadRequest(BaseModel):
    title: str | None = None
    transcript_text: str
    source: str | None = None


class ActionItemOut(BaseModel):
    id: uuid.UUID
    raw_text: str
    assigned_to_user_id: uuid.UUID | None
    priority: int
    estimated_hours: float | None
    task_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class MeetingTranscriptOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    source: str | None
    uploaded_at: datetime
    action_items: list[ActionItemOut] = []

    model_config = {"from_attributes": True}


class MeetingApplyRequest(BaseModel):
    goal_id: uuid.UUID
    action_item_ids: list[uuid.UUID] | None = None  # None = apply all
