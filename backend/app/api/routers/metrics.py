from datetime import datetime, timedelta, timezone
from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.db.session import DBSession
from app.schemas.metrics import UserFeaturesResponse
from app.services import behavior_service

router = APIRouter(prefix="/metrics", tags=["metrics"])

STALENESS_THRESHOLD = timedelta(days=1)


@router.get("/me", response_model=UserFeaturesResponse)
def get_my_metrics(db: DBSession, current_user: CurrentUser):
    """Return current user's behavioral features, recomputing if stale (>1 day)."""
    features = behavior_service.get_user_features(db, current_user.id)

    last_computed = features.last_computed_at if features else None
    if last_computed is not None and last_computed.tzinfo is None:
        last_computed = last_computed.replace(tzinfo=timezone.utc)

    stale = (
        features is None
        or last_computed is None
        or datetime.now(timezone.utc) - last_computed > STALENESS_THRESHOLD
    )

    if stale:
        features = behavior_service.update_user_features(db, current_user.id)

    return features
