import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserFeatures(Base, TimestampMixin):
    __tablename__ = "user_features"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    completion_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimation_bias_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    focus_probability_by_hour: Mapped[dict | None] = mapped_column(JSON)
    reschedule_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    burnout_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
