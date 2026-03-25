import uuid
from datetime import datetime

from pydantic import BaseModel


class TeamCreate(BaseModel):
    name: str


class TeamUpdate(BaseModel):
    name: str | None = None


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    organization_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    user_id: uuid.UUID
    is_admin: bool = False
