import uuid
from datetime import date

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ScopedMixin, TimestampMixin


class Goal(Base, TimestampMixin, ScopedMixin):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    success_metric_type: Mapped[str | None] = mapped_column(String(100))
    target_value: Mapped[float | None] = mapped_column(Float)
    target_date: Mapped[date | None]
    priority_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    min_weekly_hours: Mapped[float | None] = mapped_column(Float)
    max_weekly_hours: Mapped[float | None] = mapped_column(Float)
    constraints: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
