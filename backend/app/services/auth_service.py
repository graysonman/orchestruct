import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_user_by_google_id(db: Session, google_id: str) -> User | None:
    return db.scalar(select(User).where(User.google_id == google_id))


def create_user(db: Session, email: str, password: str, full_name: str | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_or_update_google_user(
    db: Session,
    google_id: str,
    email: str,
    full_name: str | None,
    access_token: str,
    refresh_token: str | None,
    expires_at: datetime,
) -> User:
    """Create a new user from Google OAuth or link Google to an existing account.

    Resolution order:
    1. User already linked this Google account → update tokens, return
    2. User registered with the same email → link Google to existing account
    3. New user → create account with hashed_password=None (Google-only)
    """
    user = get_user_by_google_id(db, google_id)

    if not user:
        user = get_user_by_email(db, email)

    if user:
        # Link or refresh — update Google tokens on the existing account
        user.google_id = google_id
        user.google_access_token = access_token
        if refresh_token:
            user.google_refresh_token = refresh_token
        user.google_token_expires_at = expires_at
    else:
        # Brand new user — no password (Google-only account)
        user = User(
            id=uuid.uuid4(),
            email=email,
            full_name=full_name,
            hashed_password=None,
            google_id=google_id,
            google_access_token=access_token,
            google_refresh_token=refresh_token,
            google_token_expires_at=expires_at,
        )
        db.add(user)

    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> str | None:
    user = get_user_by_email(db, email)
    if not user or not user.is_active or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return create_access_token(str(user.id))

