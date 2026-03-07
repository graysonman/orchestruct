import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.db.session import DBSession
from app.models.base import ScopeType
from app.schemas.plans import PlanGenerate, PlanResponse
from app.services import plan_service

router = APIRouter(prefix="/plans", tags=["plans"])

@router.post("/generate", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(payload: PlanGenerate, db: DBSession, current_user: CurrentUser):
    plan = plan_service.generate_plan(db, ScopeType.USER, current_user.id, payload.planning_window_start, payload.planning_window_end)
    return plan

@router.get("/{plan_id}", response_model=PlanResponse)
def get_plan(plan_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    plan = plan_service.get_plan(db, plan_id)
    if not plan or plan.scope_id != current_user.id:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan

@router.post("/{plan_id}/approve", response_model=PlanResponse)
def plan_approve(plan_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    plan = plan_service.get_plan(db, plan_id)
    if not plan or plan.scope_id != current_user.id:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status != "proposed":
        raise HTTPException(status_code=400, detail="Plan is not in proposed state")
    plan = plan_service.approve_plan(db, plan)
    return plan

@router.post("/{plan_id}/reject", response_model=PlanResponse)
def plan_reject(plan_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    plan = plan_service.get_plan(db, plan_id)
    if not plan or plan.scope_id != current_user.id:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status not in ("proposed", "approved"):
        raise HTTPException(status_code=400, detail="Plan cannot be rejected")
    plan = plan_service.reject_plan(db, plan)
    return plan
    