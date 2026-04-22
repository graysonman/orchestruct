import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.db.session import DBSession
from app.schemas.meetings import MeetingApplyRequest, MeetingTranscriptOut, MeetingUploadRequest
from app.services import meeting_service

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/upload", response_model=MeetingTranscriptOut, status_code=status.HTTP_201_CREATED)
def upload_transcript(payload: MeetingUploadRequest, db: DBSession, current_user: CurrentUser):
    meeting = meeting_service.create_transcript(
        db=db,
        user_id=current_user.id,
        title=payload.title,
        transcript_text=payload.transcript_text,
        source=payload.source,
    )
    raw_items = meeting_service.extract_action_items(meeting.transcript_text)
    action_items = meeting_service.save_action_items(db=db, meeting_id=meeting.id, items=raw_items)
    return MeetingTranscriptOut(
        id=meeting.id,
        user_id=meeting.user_id,
        title=meeting.title,
        source=meeting.source,
        uploaded_at=meeting.uploaded_at,
        action_items=action_items,
    )


@router.get("/{meeting_id}", response_model=MeetingTranscriptOut)
def get_transcript(meeting_id: uuid.UUID, db: DBSession, current_user: CurrentUser):
    meeting = meeting_service.get_transcript(db=db, meeting_id=meeting_id, user_id=current_user.id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    action_items = meeting_service.get_action_items(db=db, meeting_id=meeting.id)
    return MeetingTranscriptOut(
        id=meeting.id,
        user_id=meeting.user_id,
        title=meeting.title,
        source=meeting.source,
        uploaded_at=meeting.uploaded_at,
        action_items=action_items,
    )


@router.post("/{meeting_id}/apply", status_code=status.HTTP_200_OK)
def apply_transcript(
    meeting_id: uuid.UUID,
    payload: MeetingApplyRequest,
    db: DBSession,
    current_user: CurrentUser,
):
    meeting = meeting_service.get_transcript(db=db, meeting_id=meeting_id, user_id=current_user.id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    created_tasks = meeting_service.apply_action_items(
        db=db,
        meeting_id=meeting_id,
        goal_id=payload.goal_id,
        user=current_user,
        selected_ids=payload.action_item_ids,
    )
    return {"tasks_created": len(created_tasks), "task_ids": [str(t.id) for t in created_tasks]}
