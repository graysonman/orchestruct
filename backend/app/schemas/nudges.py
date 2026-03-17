import uuid
from datetime import datetime

from pydantic import BaseModel


class NudgeResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    nudge_type: str
    message: str
    trigger_data: dict | None
    status: str
    acknowledged_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
