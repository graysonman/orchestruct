import uuid

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser
from app.db.session import DBSession
from app.schemas.nudges import NudgeResponse
from app.services import nudge_service

router = APIRouter(prefix="/nudges", tags=["nudges"])


@router.post("/evaluate", response_model=list[NudgeResponse], status_code=201)
def evaluate_nudges(db: DBSession, current_user: CurrentUser):
    """Run nudge evaluation for the current user. Returns newly created nudges."""
    return nudge_service.evaluate_nudges(db, current_user.id)


@router.get("", response_model=list[NudgeResponse])
def list_nudges(db: DBSession, current_user: CurrentUser, status: str | None = None):
    """List nudges for the current user, optionally filtered by status."""
    return nudge_service.get_nudges(db, current_user.id, status=status)


@router.get("/{nudge_id}", response_model=NudgeResponse)
def get_nudge(nudge_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    nudge = nudge_service.get_nudge(db, nudge_id)
    if not nudge or nudge.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Nudge not found")
    return nudge


@router.post("/{nudge_id}/acknowledge", response_model=NudgeResponse)
def acknowledge_nudge(nudge_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    nudge = nudge_service.get_nudge(db, nudge_id)
    if not nudge or nudge.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Nudge not found")
    return nudge_service.acknowledge_nudge(db, nudge)


@router.post("/{nudge_id}/dismiss", response_model=NudgeResponse)
def dismiss_nudge(nudge_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    nudge = nudge_service.get_nudge(db, nudge_id)
    if not nudge or nudge.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Nudge not found")
    return nudge_service.dismiss_nudge(db, nudge)
