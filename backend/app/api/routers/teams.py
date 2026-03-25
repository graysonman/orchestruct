import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.db.session import DBSession
from app.models.team import Team
from app.schemas.teams import AddMemberRequest, MemberResponse, TeamCreate, TeamResponse, TeamUpdate
from app.services import team_service

router = APIRouter(prefix="/teams", tags=["teams"])


def _require_member(db, team_id: uuid.UUID, user_id: uuid.UUID) -> Team:
    """Get team and verify current user is a member, or raise 404."""
    team = team_service.get_team(db, team_id)
    if not team or not team_service.check_is_member(db, team_id, user_id):
        raise HTTPException(status_code=404, detail="Team not found")
    return team


def _require_admin(db, team_id: uuid.UUID, user_id: uuid.UUID) -> Team:
    """Get team and verify current user is an admin, or raise 403."""
    team = team_service.get_team(db, team_id)
    if not team or not team_service.check_is_member(db, team_id, user_id):
        raise HTTPException(status_code=404, detail="Team not found")
    if not team_service.check_is_admin(db, team_id, user_id):
        raise HTTPException(status_code=403, detail="Admin access required")
    return team


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamCreate, db: DBSession, current_user: CurrentUser):
    return team_service.create_team(db, name=payload.name, creator_id=current_user.id)


@router.get("", response_model=list[TeamResponse])
def list_teams(db: DBSession, current_user: CurrentUser):
    return team_service.list_user_teams(db, current_user.id)


@router.get("/{team_id}", response_model=TeamResponse)
def get_team(team_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    return _require_member(db, team_id, current_user.id)


@router.patch("/{team_id}", response_model=TeamResponse)
def update_team(team_id: uuid.UUID, payload: TeamUpdate, db: DBSession, current_user: CurrentUser):
    team = _require_admin(db, team_id, current_user.id)
    if payload.name is not None:
        team.name = payload.name
        db.commit()
        db.refresh(team)
    return team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(team_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    team = _require_admin(db, team_id, current_user.id)
    db.delete(team)
    db.commit()


@router.get("/{team_id}/members", response_model=list[MemberResponse])
def list_members(team_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    _require_member(db, team_id, current_user.id)
    return team_service.list_members(db, team_id)


@router.post("/{team_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(team_id: uuid.UUID, payload: AddMemberRequest, db: DBSession, current_user: CurrentUser):
    _require_admin(db, team_id, current_user.id)
    return team_service.add_member(db, team_id, payload.user_id, payload.is_admin)


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(team_id: uuid.UUID, user_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    _require_admin(db, team_id, current_user.id)
    team_service.remove_member(db, team_id, user_id)
