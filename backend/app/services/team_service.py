"""Team management service."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import ScopeType
from app.models.team import Team
from app.models.team_membership import TeamMembership


def create_team(db: Session, name: str, creator_id: uuid.UUID) -> Team:
    """Create a new team and add the creator as an admin member.

    Args:
        db: SQLAlchemy session
        name: Team name
        creator_id: UUID of the user creating the team (becomes admin)

    Returns:
        The newly created Team
    """
    team_id = uuid.uuid4()
    new_team = Team(
        id=team_id,
        name=name,
        scope_type=ScopeType.TEAM,
        scope_id=team_id,  # team scopes itself
    )
    db.add(new_team)
    membership = TeamMembership(
        id=uuid.uuid4(),
        team_id=new_team.id,
        user_id=creator_id,
        is_admin=True,
        scope_type=ScopeType.TEAM,
        scope_id=new_team.id,
    )
    db.add(membership)
    db.commit()
    db.refresh(new_team)
    return new_team


def get_team(db: Session, team_id: uuid.UUID) -> Team | None:
    """Get a team by ID."""
    return db.get(Team, team_id)


def list_user_teams(db: Session, user_id: uuid.UUID) -> list[Team]:
    """Return all teams the user is a member of."""
    return list(db.scalars(
        select(Team)
        .join(TeamMembership, TeamMembership.team_id == Team.id)
        .where(TeamMembership.user_id == user_id)
    ))


def add_member(
    db: Session,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    is_admin: bool = False,
) -> TeamMembership:
    """Add a user to a team. Raises 400 if already a member."""
    existing = db.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member of this team")

    membership = TeamMembership(
        id=uuid.uuid4(),
        team_id=team_id,
        user_id=user_id,
        is_admin=is_admin,
        scope_type=ScopeType.TEAM,
        scope_id=team_id,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def remove_member(db: Session, team_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Remove a user from a team.

    Guards:
    - Raises 404 if the membership doesn't exist.
    - Raises 400 if removing this member would leave the team with no admins.
    """
    membership = db.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
        )
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    if membership.is_admin:
        admin_count = db.scalar(
            select(TeamMembership)
            .where(
                TeamMembership.team_id == team_id,
                TeamMembership.is_admin == True,  # noqa: E712
            )
        )
        admins = list(db.scalars(
            select(TeamMembership).where(
                TeamMembership.team_id == team_id,
                TeamMembership.is_admin == True,  # noqa: E712
            )
        ))
        if len(admins) <= 1:
            raise HTTPException(
                status_code=400, detail="Cannot remove the last admin from a team"
            )

    db.delete(membership)
    db.commit()


def list_members(db: Session, team_id: uuid.UUID) -> list[TeamMembership]:
    """Return all memberships for a team."""
    return list(db.scalars(
        select(TeamMembership).where(TeamMembership.team_id == team_id)
    ))


def check_is_member(db: Session, team_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Return True if the user is a member of the team."""
    result = db.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
        )
    )
    return result is not None


def check_is_admin(db: Session, team_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Return True if the user is an admin of the team."""
    result = db.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
            TeamMembership.is_admin == True,  # noqa: E712
        )
    )
    return result is not None
