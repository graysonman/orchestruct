"""Google OAuth endpoints.

GET /auth/google          → returns authorization URL (redirect user here)
GET /auth/google/callback → exchanges code for tokens, returns JWT
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import DBSession
from app.services import auth_service
from app.services import google_calendar_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_google_configured():
    """Raise 501 if Google OAuth credentials are not set in config."""
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured on this server",
        )


@router.get("/google")
def google_authorize():
    """Return the Google OAuth consent page URL.

    The frontend should redirect the user to this URL.
    After consent, Google redirects to GOOGLE_REDIRECT_URI with ?code=...
    """
    _require_google_configured()
    state = secrets.token_urlsafe(16)
    authorization_url = google_calendar_service.get_authorization_url(state)
    return {"authorization_url": authorization_url, "state": state}


@router.get("/google/callback")
def google_callback(
    db: DBSession,
    code: str = Query(...),
    state: str = Query(default=""),
):
    """Exchange Google authorization code for tokens, create/link user, return JWT.

    This endpoint receives the redirect from Google after the user approves
    the OAuth consent screen. It:
    1. Exchanges the code for access + refresh tokens
    2. Fetches the user's Google profile (email, name, google_id)
    3. Creates a new Orchestruct account OR links to an existing one
    4. Returns a JWT in the same format as /auth/login

    The frontend can treat this response identically to a normal login.
    """
    _require_google_configured()

    try:
        token_data = google_calendar_service.exchange_code_for_tokens(code)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange authorization code with Google",
        )

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    try:
        google_user = google_calendar_service.get_google_user_info(access_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to fetch user info from Google",
        )

    user = auth_service.create_or_update_google_user(
        db,
        google_id=google_user["id"],
        email=google_user["email"],
        full_name=google_user.get("name"),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )

    jwt = create_access_token(str(user.id))
    return {"access_token": jwt, "token_type": "bearer"}
