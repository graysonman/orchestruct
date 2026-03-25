import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.api.routers.goals import can_access_scoped_record
from app.db.session import DBSession
from app.models.base import ScopeType
from app.schemas.plans import PlanGenerate, PlanResponse
from app.services import plan_service, team_service
from app.services.scheduler import ValidationError

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("/generate", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(payload: PlanGenerate, db: DBSession, current_user: CurrentUser):
    """Generate a new plan for the current user or a team.

    For user plans: scope defaults to current user.
    For team plans: current user must be a team member.
    """
    scope_type = payload.scope_type
    scope_id = payload.scope_id

    if scope_type == ScopeType.TEAM:
        if scope_id is None:
            raise HTTPException(status_code=422, detail="scope_id required for team plans")
        if not team_service.check_is_member(db, scope_id, current_user.id):
            raise HTTPException(status_code=403, detail="Not a member of this team")
    else:
        scope_id = current_user.id

    try:
        plan = plan_service.generate_plan(
            db,
            scope_type,
            scope_id,
            payload.planning_window_start,
            payload.planning_window_end,
        )
        return plan
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": e.errors},
        )


@router.get("/{plan_id}", response_model=PlanResponse)
def get_plan(plan_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    plan = plan_service.get_plan(db, plan_id)
    if not plan or not can_access_scoped_record(db, plan, current_user):
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post("/{plan_id}/approve", response_model=PlanResponse)
def plan_approve(plan_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    plan = plan_service.get_plan(db, plan_id)
    if not plan or not can_access_scoped_record(db, plan, current_user):
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status != "proposed":
        raise HTTPException(status_code=400, detail="Plan is not in proposed state")
    plan = plan_service.approve_plan(db, plan)
    return plan


@router.post("/{plan_id}/reject", response_model=PlanResponse)
def plan_reject(plan_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    plan = plan_service.get_plan(db, plan_id)
    if not plan or not can_access_scoped_record(db, plan, current_user):
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status not in ("proposed", "approved"):
        raise HTTPException(status_code=400, detail="Plan cannot be rejected")
    plan = plan_service.reject_plan(db, plan)
    return plan
