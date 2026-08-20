from datetime import date
from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.db.session import DBSession
from app.schemas.metrics import AlignmentScoreResponse, UserFeaturesResponse
from app.services import behavior_service

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/me", response_model=UserFeaturesResponse)
def get_my_metrics(db: DBSession, current_user: CurrentUser):
    """Return the current user's behavioral features.

    A plain read. Features are recomputed by the worklog endpoints whenever a
    log is written or amended, so what is stored is always current with the
    user's history — there is nothing to refresh here.

    The one exception is a user who has never logged work: they have no row
    yet, and computing one gives the expected zeroed defaults rather than a
    404 the caller would have to special-case.
    """
    features = behavior_service.get_user_features(db, current_user.id)
    if features is None:
        features = behavior_service.update_user_features(db, current_user.id)
    return features


@router.get("/alignment", response_model=AlignmentScoreResponse)
def get_alignment_score(
    week_start: date,
    week_end: date,
    db: DBSession,
    current_user: CurrentUser,
):
    """Return alignment score for the given week window."""
    return behavior_service.compute_alignment_score(db, current_user.id, week_start, week_end)
