import uuid
from datetime import time

from sqlalchemy import ForeignKey, String, Time
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserScheduleConfig(Base, TimestampMixin):
    """User's work schedule configuration.

    Stores timezone, work days, and work hours with optional per-day overrides.
    """
    __tablename__ = "user_schedule_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    work_days: Mapped[list[int]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: [0, 1, 2, 3, 4]  # Mon-Fri
    )
    work_start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(9, 0)
    )
    work_end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(17, 0)
    )
    day_overrides: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None
    )

    user = relationship("User", back_populates="schedule_config")
