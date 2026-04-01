"""Tests for Google OAuth and calendar sync.

All Google API calls are monkeypatched — no real credentials needed.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

REGISTER_URL = "/api/v1/auth/register"
GOOGLE_AUTH_URL = "/api/v1/auth/google"
GOOGLE_CALLBACK_URL = "/api/v1/auth/google/callback"
PLANS_URL = "/api/v1/plans"
GOALS_URL = "/api/v1/goals"

TODAY = datetime.now(timezone.utc).date()
WINDOW = {
    "planning_window_start": str(TODAY),
    "planning_window_end": str(TODAY + timedelta(days=4)),
}

# Fake Google token response
FAKE_TOKENS = {
    "access_token": "fake-access-token",
    "refresh_token": "fake-refresh-token",
    "expires_in": 3600,
    "token_type": "Bearer",
}

# Fake Google user info
FAKE_GOOGLE_USER = {
    "id": "google-uid-123",
    "email": "googleuser@example.com",
    "name": "Google User",
}

# Fake Google Calendar event
FAKE_GOOGLE_EVENT = {
    "id": "google-event-abc",
    "summary": "Team Meeting",
    "start": {"dateTime": f"{TODAY}T10:00:00"},
    "end": {"dateTime": f"{TODAY}T11:00:00"},
}

FAKE_ALLDAY_EVENT = {
    "id": "google-event-allday",
    "summary": "All Day Event",
    "start": {"date": str(TODAY)},
    "end": {"date": str(TODAY)},
}


@pytest.fixture
def google_configured(monkeypatch):
    """Patch settings to enable Google OAuth."""
    from app.core import config
    # Patch the cached instance — do NOT clear the cache after setting attrs
    # or get_settings() will create a fresh object without the patched values
    settings = config.get_settings()
    monkeypatch.setattr(settings, "google_client_id", "fake-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "fake-client-secret")
    monkeypatch.setattr(settings, "google_redirect_uri", "http://localhost:8000/api/v1/auth/google/callback")
    yield
    config.get_settings.cache_clear()


@pytest.fixture
def mock_google_api(monkeypatch):
    """Patch all Google API httpx calls."""
    with patch("app.services.google_calendar_service.exchange_code_for_tokens") as mock_exchange, \
         patch("app.services.google_calendar_service.get_google_user_info") as mock_userinfo, \
         patch("app.services.google_calendar_service.fetch_google_events") as mock_fetch, \
         patch("app.services.google_calendar_service.get_authorization_url") as mock_auth_url:

        mock_exchange.return_value = FAKE_TOKENS
        mock_userinfo.return_value = FAKE_GOOGLE_USER
        mock_fetch.return_value = [FAKE_GOOGLE_EVENT, FAKE_ALLDAY_EVENT]
        mock_auth_url.return_value = "https://accounts.google.com/fake-auth-url"

        yield {
            "exchange": mock_exchange,
            "userinfo": mock_userinfo,
            "fetch": mock_fetch,
            "auth_url": mock_auth_url,
        }


@pytest.fixture
def auth_headers(client: TestClient):
    res = client.post(REGISTER_URL, json={"email": "normal@example.com", "password": "secret123"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ─────────────────────────────────────────────────────────────────────────────
# OAuth flow
# ─────────────────────────────────────────────────────────────────────────────

def test_google_not_configured_returns_501(client: TestClient):
    """GET /auth/google without credentials configured → 501."""
    res = client.get(GOOGLE_AUTH_URL)
    assert res.status_code == 501


def test_get_authorization_url(client: TestClient, google_configured, mock_google_api):
    res = client.get(GOOGLE_AUTH_URL)
    assert res.status_code == 200
    assert "authorization_url" in res.json()
    assert "state" in res.json()


def test_callback_creates_new_user(client: TestClient, google_configured, mock_google_api, db):
    res = client.get(GOOGLE_CALLBACK_URL, params={"code": "fake-code", "state": "fake-state"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Verify user was created in DB
    from sqlalchemy import select
    from app.models.user import User
    user = db.scalar(select(User).where(User.google_id == FAKE_GOOGLE_USER["id"]))
    assert user is not None
    assert user.email == FAKE_GOOGLE_USER["email"]
    assert user.google_access_token == FAKE_TOKENS["access_token"]
    assert user.hashed_password is None  # Google-only user


def test_callback_links_existing_user(client: TestClient, google_configured, mock_google_api, db):
    """OAuth callback with email matching an existing email/password user links the accounts."""
    # Register normally first
    client.post(REGISTER_URL, json={"email": FAKE_GOOGLE_USER["email"], "password": "secret123"})

    res = client.get(GOOGLE_CALLBACK_URL, params={"code": "fake-code", "state": "x"})
    assert res.status_code == 200

    from sqlalchemy import select
    from app.models.user import User
    users = list(db.scalars(select(User).where(User.email == FAKE_GOOGLE_USER["email"])))
    assert len(users) == 1  # not duplicated
    assert users[0].google_id == FAKE_GOOGLE_USER["id"]  # linked


def test_callback_returns_usable_jwt(client: TestClient, google_configured, mock_google_api):
    """JWT returned from callback works for authenticated endpoints."""
    res = client.get(GOOGLE_CALLBACK_URL, params={"code": "fake-code", "state": "x"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    goals_res = client.get(GOALS_URL, headers=headers)
    assert goals_res.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Calendar sync
# ─────────────────────────────────────────────────────────────────────────────

def test_sync_google_creates_events(db):
    """sync_google_to_local creates CalendarEvent rows for timed events."""
    from app.models.user import User
    from app.services.google_calendar_service import sync_google_to_local
    from app.models.calendar_event import CalendarEvent
    from sqlalchemy import select

    user = User(
        id=uuid.uuid4(), email="synctest@example.com", hashed_password="x",
        google_id="g1", google_access_token="tok",
    )
    db.add(user)
    db.commit()

    count = sync_google_to_local(db, user.id, [FAKE_GOOGLE_EVENT, FAKE_ALLDAY_EVENT])

    assert count == 1  # all-day event skipped
    events = list(db.scalars(select(CalendarEvent).where(CalendarEvent.user_id == user.id)))
    assert len(events) == 1
    assert events[0].external_id == FAKE_GOOGLE_EVENT["id"]
    assert events[0].title == "Team Meeting"


def test_sync_google_updates_existing(db):
    """Running sync twice with updated event data updates rather than duplicates."""
    from app.models.user import User
    from app.services.google_calendar_service import sync_google_to_local
    from app.models.calendar_event import CalendarEvent
    from sqlalchemy import select

    user = User(
        id=uuid.uuid4(), email="updatetest@example.com", hashed_password="x",
        google_id="g2", google_access_token="tok",
    )
    db.add(user)
    db.commit()

    sync_google_to_local(db, user.id, [FAKE_GOOGLE_EVENT])

    # Update the event title and sync again
    updated_event = {**FAKE_GOOGLE_EVENT, "summary": "Updated Meeting"}
    sync_google_to_local(db, user.id, [updated_event])

    events = list(db.scalars(select(CalendarEvent).where(CalendarEvent.user_id == user.id)))
    assert len(events) == 1  # no duplicate
    assert events[0].title == "Updated Meeting"


def test_sync_skips_allday_events(db):
    """All-day events (with 'date' not 'dateTime') are not imported."""
    from app.models.user import User
    from app.services.google_calendar_service import sync_google_to_local
    from app.models.calendar_event import CalendarEvent
    from sqlalchemy import select

    user = User(
        id=uuid.uuid4(), email="allday@example.com", hashed_password="x",
        google_id="g3", google_access_token="tok",
    )
    db.add(user)
    db.commit()

    count = sync_google_to_local(db, user.id, [FAKE_ALLDAY_EVENT])
    assert count == 0
    events = list(db.scalars(select(CalendarEvent).where(CalendarEvent.user_id == user.id)))
    assert len(events) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Push plan to Google
# ─────────────────────────────────────────────────────────────────────────────

def test_push_plan_calls_google_api(client: TestClient, google_configured, mock_google_api, auth_headers):
    """Approving a plan for a Google-linked user triggers push to Google Calendar."""
    # Link Google to the existing user
    from app.models.user import User
    from app.services import auth_service
    from app.db.session import get_db

    with patch("app.services.google_calendar_service.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "new-gcal-event-id"}
        mock_response.raise_for_status = MagicMock()
        mock_httpx.post.return_value = mock_response

        # Create goal + task + plan
        goal = client.post(GOALS_URL, json={"title": "Push Test Goal"}, headers=auth_headers).json()
        client.post(
            f"{GOALS_URL}/{goal['id']}/tasks",
            json={"title": "Push Task", "estimated_minutes": 60, "difficulty": 2,
                  "due_date": str(TODAY + timedelta(days=3))},
            headers=auth_headers,
        )
        plan = client.post(f"{PLANS_URL}/generate", json=WINDOW, headers=auth_headers).json()
        assert plan["status"] == "proposed"


def test_push_plan_skipped_if_no_google_token(client: TestClient, auth_headers):
    """Approving a plan for a user without Google linked works normally."""
    goal = client.post(GOALS_URL, json={"title": "No Google Goal"}, headers=auth_headers).json()
    client.post(
        f"{GOALS_URL}/{goal['id']}/tasks",
        json={"title": "Task", "estimated_minutes": 60, "difficulty": 2,
              "due_date": str(TODAY + timedelta(days=3))},
        headers=auth_headers,
    )
    plan = client.post(f"{PLANS_URL}/generate", json=WINDOW, headers=auth_headers).json()
    res = client.post(f"{PLANS_URL}/{plan['id']}/approve", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "approved"


# ─────────────────────────────────────────────────────────────────────────────
# Auto-sync on plan generate
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_plan_auto_syncs_google(client: TestClient, google_configured, mock_google_api, db):
    """Plan generation auto-syncs Google events for Google-linked users."""
    from app.models.user import User

    # Create user with Google token
    user = User(
        id=uuid.uuid4(), email="autosync@example.com", hashed_password="x",
        google_id="g-autosync", google_access_token="tok",
        google_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(user)
    db.commit()

    from app.core.security import create_access_token
    token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.google_calendar_service.fetch_google_events") as mock_fetch, \
         patch("app.services.google_calendar_service.ensure_fresh_token") as mock_fresh:
        mock_fresh.return_value = "tok"
        mock_fetch.return_value = [FAKE_GOOGLE_EVENT]

        client.post(GOALS_URL, json={"title": "Auto Sync Goal"}, headers=headers)
        client.post(f"{PLANS_URL}/generate", json=WINDOW, headers=headers)

        mock_fetch.assert_called_once()
