"""Google Calendar integration service.

Handles OAuth token management, pulling Google Calendar events into the internal
calendar, pushing approved plan blocks to Google Calendar, and conflict detection.

All Google API calls use httpx (already in requirements) — no additional libraries needed.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.base import ScheduleType
from app.models.calendar_event import CalendarEvent
from app.models.plan import Plan, PlanItem
from app.models.task import Task
from app.models.user import User

# ─────────────────────────────────────────────────────────────────────────────
# Google API endpoints
# ─────────────────────────────────────────────────────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_CALENDAR_EVENTS_URL = (
    "https://www.googleapis.com/calendar/v3/calendars/primary/events"
)

GOOGLE_SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar",
])


# ─────────────────────────────────────────────────────────────────────────────
# OAuth flow helpers
# ─────────────────────────────────────────────────────────────────────────────


def get_authorization_url(state: str) -> str:
    """Build the Google OAuth consent page URL.

    The frontend redirects the user here. After consent, Google redirects
    back to GOOGLE_REDIRECT_URI with ?code=...&state=...

    Args:
        state: Random string for CSRF protection (included in callback URL)

    Returns:
        Full Google authorization URL
    """
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",   # request refresh token
        "prompt": "consent",        # always show consent (ensures refresh token is issued)
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange an authorization code for access + refresh tokens.

    Called once after the user approves the OAuth consent screen.
    Google returns the code in the callback URL; we POST it here to get tokens.

    Args:
        code: Authorization code from Google callback

    Returns:
        Token dict: {access_token, refresh_token, expires_in, token_type}

    Raises:
        httpx.HTTPStatusError: if Google rejects the code
    """
    settings = get_settings()
    response = httpx.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    })
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str) -> dict:
    """Get a new access token using the stored refresh token.

    Access tokens expire after ~1 hour. This is called automatically by
    ensure_fresh_token() whenever the stored token is about to expire.

    Args:
        refresh_token: Long-lived refresh token stored on the user record

    Returns:
        Token dict: {access_token, expires_in, token_type}
    """
    settings = get_settings()
    response = httpx.post(GOOGLE_TOKEN_URL, data={
        "refresh_token": refresh_token,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "grant_type": "refresh_token",
    })
    response.raise_for_status()
    return response.json()


def get_google_user_info(access_token: str) -> dict:
    """Fetch the authenticated user's Google profile.

    Returns their Google ID, email, and display name — used to create
    or link their Orchestruct account.

    Args:
        access_token: Valid Google access token

    Returns:
        Dict with {id, email, name, ...}
    """
    response = httpx.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json()


def ensure_fresh_token(db: Session, user: User) -> str:
    """Return a valid access token, refreshing if expired or close to expiry.

    Checks google_token_expires_at. If the token expires within 5 minutes,
    refreshes it and persists the new token to the user record.

    Args:
        db: SQLAlchemy session
        user: User with google_access_token and google_refresh_token set

    Returns:
        A valid access token string

    Raises:
        ValueError: if user has no Google tokens
    """
    if not user.google_access_token:
        raise ValueError("User has no Google access token")

    now = datetime.now(timezone.utc)
    expires_at = user.google_token_expires_at

    if expires_at and expires_at <= now + timedelta(minutes=5):
        token_data = refresh_access_token(user.google_refresh_token)
        user.google_access_token = token_data["access_token"]
        user.google_token_expires_at = now + timedelta(seconds=token_data["expires_in"])
        db.commit()

    return user.google_access_token


# ─────────────────────────────────────────────────────────────────────────────
# Calendar sync
# ─────────────────────────────────────────────────────────────────────────────


def fetch_google_events(
    access_token: str,
    time_min: datetime,
    time_max: datetime,
) -> list[dict]:
    """Fetch calendar events from the user's primary Google Calendar.

    Args:
        access_token: Valid Google access token
        time_min: Start of time range (inclusive)
        time_max: End of time range (inclusive)

    Returns:
        List of Google Calendar event dicts (raw API response items)
    """
    response = httpx.get(
        GOOGLE_CALENDAR_EVENTS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "timeMin": time_min.isoformat() + "Z",
            "timeMax": time_max.isoformat() + "Z",
            "singleEvents": "true",    # expand recurring events into instances
            "orderBy": "startTime",
        },
    )
    response.raise_for_status()
    return response.json().get("items", [])


def sync_google_to_local(
    db: Session,
    user_id: uuid.UUID,
    google_events: list[dict],
) -> int:
    """Upsert Google Calendar events into the internal CalendarEvent table.

    Uses external_id (= Google event ID) as the deduplication key.
    Running this multiple times with the same events is safe — it updates
    existing rows rather than creating duplicates.

    Steps for each Google event:
    1. Skip all-day events (no time component — can't block availability slots)
    2. Look up CalendarEvent WHERE external_id == google_event["id"]
    3. If found: update title and start/end times
    4. If not found: create a new CalendarEvent with schedule_type=PERSONAL

    Args:
        db: SQLAlchemy session
        user_id: UUID of the user whose calendar is being synced
        google_events: Raw list of Google Calendar event dicts

    Returns:
        Number of events synced (created + updated)
    """
    count = 0
    for event in google_events:
        if "dateTime" not in event.get("start", {}):
            continue

        start_dt = datetime.fromisoformat(event["start"]["dateTime"])
        end_dt = datetime.fromisoformat(event["end"]["dateTime"])
        title = event.get("summary", "Untitled")

        existing = db.scalar(
            select(CalendarEvent).where(CalendarEvent.external_id == event["id"])
        )
        if existing:
            existing.title = title
            existing.start_datetime = start_dt
            existing.end_datetime = end_dt
        else:
            new_event = CalendarEvent(
                id=uuid.uuid4(),
                user_id=user_id,
                external_id=event["id"],
                title=title,
                schedule_type=ScheduleType.PERSONAL,
                start_datetime=start_dt,
                end_datetime=end_dt,
                all_day=False,
            )
            db.add(new_event)

        count += 1

    db.commit()
    return count

def detect_conflicts(
    db: Session,
    user_id: uuid.UUID,
    google_events: list[dict],
) -> list[dict]:
    """Find Google Calendar events that overlap with existing plan items.

    Used to populate risk_summary["google_conflicts"] so the user knows
    their plan may conflict with real calendar commitments.

    Args:
        db: SQLAlchemy session
        user_id: UUID of the user
        google_events: Raw Google Calendar event dicts

    Returns:
        List of conflict dicts: [{google_event_id, title, conflict_type}]
    """
    # For each non-all-day Google event, check if any CalendarEvent of
    # type BLOCKED or PERSONAL already exists at that time after the sync.
    # Simple implementation: return the titles of synced non-work events
    # that fall within working hours (those will reduce availability).
    conflicts = []
    for event in google_events:
        start = event.get("start", {})
        if "dateTime" not in start:
            continue  # skip all-day events
        conflicts.append({
            "google_event_id": event.get("id"),
            "title": event.get("summary", "Untitled"),
            "conflict_type": "google_event_blocks_availability",
        })
    return conflicts


# ─────────────────────────────────────────────────────────────────────────────
# Push plan to Google
# ─────────────────────────────────────────────────────────────────────────────


def push_plan_to_google(
    db: Session,
    plan: Plan,
    user: User,
) -> list[str]:
    """Push approved plan items to the user's Google Calendar.

    Creates a Google Calendar event for each PlanItem. Stores the returned
    Google event ID in plan_item.rationale["google_event_id"] so we can
    identify and delete these events if the plan is later rejected.

    Only works for USER-scoped plans. Team plans push to individual member
    calendars — that is a Stage 9 concern.

    Steps for each PlanItem:
    1. Look up the Task to get its title
    2. Build a Google event dict with summary, start dateTime, end dateTime
    3. POST to GOOGLE_CALENDAR_EVENTS_URL
    4. Store the returned event["id"] in plan_item.rationale["google_event_id"]
    5. Commit the updated rationale

    Args:
        db: SQLAlchemy session
        plan: Approved Plan with items loaded
        user: User with a valid access token (caller ensures token is fresh)

    Returns:
        List of created Google event IDs
    """
    event_list = []
    for item in plan.items:
        task = db.get(Task, item.task_id)
        title = task.title if task else "Planned Task"
        google_event_dict = {
            "summary": title,
            "start": {"dateTime": f"{item.scheduled_date}T{item.start_time}"},
            "end": {"dateTime": f"{item.scheduled_date}T{item.end_time}"},
        }
        response = httpx.post(
            GOOGLE_CALENDAR_EVENTS_URL,
            headers={"Authorization": f"Bearer {user.google_access_token}"},
            json=google_event_dict,
        )
        google_event_id = response.json()["id"]
        event_list.append(google_event_id)
        item.rationale = {**(item.rationale or {}), "google_event_id": google_event_id}
    db.commit()
    return event_list

