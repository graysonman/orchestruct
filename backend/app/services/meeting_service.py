import json
import os
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.meeting import ExtractedActionItem, MeetingTranscript
from app.models.task import Task
from app.models.base import ScopeType
from app.models.user import User


def create_transcript(
    db: Session,
    user_id: uuid.UUID,
    title: str | None,
    transcript_text: str,
    source: str | None,
) -> MeetingTranscript:
    meeting = MeetingTranscript(
        user_id=user_id,
        title=title,
        transcript_text=transcript_text,
        source=source,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


def extract_action_items(transcript_text: str) -> list[dict]:
    """
    Call the LLM API with the transcript and return a list of action items.

    Each item in the returned list should be a dict with keys:
        - text (str): the action item text
        - priority (int): 1–5, where 5 is highest
        - estimated_hours (float | None): time estimate, or None if unknown
        - assigned_hint (str | None): a name mentioned in the transcript, or None
    """
    from openai import OpenAI
    from openai import RateLimitError, APIError

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )
    prompt = (
        "Return ONLY a valid JSON array. No explanation. No markdown fences. "
        "Each element must have: text (str), priority (int 1-5), "
        "estimated_hours (float or null), assigned_hint (str or null). "
        "Priority guide: urgent/ASAP=5, by EOD=4, this week=3, no deadline=2, low priority=1."
    )
    models = [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "google/gemma-3-27b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
    ]
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": transcript_text},
    ]
    for model in models:
        try:
            response = client.chat.completions.create(model=model, messages=messages)
            response_text = response.choices[0].message.content
            data = json.loads(response_text)
            return data
        except (RateLimitError, APIError):
            continue
        except (json.JSONDecodeError, Exception):
            return []
    return []

def save_action_items(
    db: Session,
    meeting_id: uuid.UUID,
    items: list[dict],
) -> list[ExtractedActionItem]:
    rows = []
    for item in items:
        row = ExtractedActionItem(
            meeting_id=meeting_id,
            raw_text=item.get("text", ""),
            priority=int(item.get("priority", 3)),
            estimated_hours=item.get("estimated_hours"),
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def apply_action_items(
    db: Session,
    meeting_id: uuid.UUID,
    goal_id: uuid.UUID,
    user: User,
    selected_ids: list[uuid.UUID] | None = None,
    window_start: date | None = None,
    window_end: date | None = None,
) -> list[Task]:
    """
    Convert extracted action items into Task rows, link them back to the action items,
    then trigger plan regeneration.
    """
    query = db.query(ExtractedActionItem).filter(
        ExtractedActionItem.meeting_id == meeting_id,
        ExtractedActionItem.task_id.is_(None),  # only unapplied items
    )
    if selected_ids is not None:
        query = query.filter(ExtractedActionItem.id.in_(selected_ids))
    action_items = query.all()

    created_tasks: list[Task] = []

    for action_item in action_items:
        new_task = Task(
            goal_id=goal_id,
            title=action_item.raw_text,
            estimated_minutes=int(action_item.estimated_hours * 60) if action_item.estimated_hours else None,
            difficulty=action_item.priority,
            owner_user_id=action_item.assigned_to_user_id or user.id,
            status="pending",
        )
        db.add(new_task)
        db.flush()
        action_item.task_id = new_task.id
        created_tasks.append(new_task)
    db.commit()

    # Trigger plan regeneration after tasks are created
    if created_tasks and window_start and window_end:
        from app.services import plan_service
        plan_service.generate_plan(
            db=db,
            scope_type=ScopeType.USER,
            scope_id=user.id,
            window_start=window_start,
            window_end=window_end,
        )

    return created_tasks


def get_transcript(
    db: Session,
    meeting_id: uuid.UUID,
    user_id: uuid.UUID,
) -> MeetingTranscript | None:
    return (
        db.query(MeetingTranscript)
        .filter(
            MeetingTranscript.id == meeting_id,
            MeetingTranscript.user_id == user_id,
        )
        .first()
    )


def get_action_items(
    db: Session,
    meeting_id: uuid.UUID,
) -> list[ExtractedActionItem]:
    return (
        db.query(ExtractedActionItem)
        .filter(ExtractedActionItem.meeting_id == meeting_id)
        .all()
    )
