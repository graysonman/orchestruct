import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ScheduleType, TimestampMixin


class CalendarEvent(Base, TimestampMixin):
    """Calendar event model with full iCalendar RRULE support.

    Supports one-time events, recurring events, and exceptions to recurring events.
    """
    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    schedule_type: Mapped[ScheduleType] = mapped_column(
        SQLEnum(ScheduleType),
        nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    start_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    end_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rrule: Mapped[str | None] = mapped_column(String(512), nullable=True)
    recurrence_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    exdates: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    parent_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=True
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user = relationship("User", back_populates="calendar_events")
    parent_event = relationship(
        "CalendarEvent",
        remote_side=[id],
        back_populates="exceptions"
    )
    exceptions = relationship(
        "CalendarEvent",
        back_populates="parent_event",
        cascade="all, delete-orphan"
    )
