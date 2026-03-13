import uuid
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.db.session import DBSession
from app.models.work_log import WorkLog
from app.schemas.worklogs import WorkLogCreate, WorkLogResponse

router = APIRouter(prefix="/worklogs", tags=["worklogs"])


def _get_owned_worklog(worklog_id: uuid.UUID, db: DBSession, current_user: CurrentUser) -> WorkLog:
    log = db.get(WorkLog, worklog_id)
    if not log or log.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="WorkLog not found")
    return log


@router.post("", response_model=WorkLogResponse, status_code=status.HTTP_201_CREATED)
def create_worklog(payload: WorkLogCreate, db: DBSession, current_user: CurrentUser):
    log = WorkLog(
        id=uuid.uuid4(),
        user_id=current_user.id,
        task_id=payload.task_id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        completed=payload.completed,
        notes=payload.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("", response_model=list[WorkLogResponse])
def list_worklogs(db: DBSession, current_user: CurrentUser):
    return list(db.scalars(select(WorkLog).where(WorkLog.user_id == current_user.id)))


@router.get("/{worklog_id}", response_model=WorkLogResponse)
def get_worklog(worklog_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    return _get_owned_worklog(worklog_id, db, current_user)
