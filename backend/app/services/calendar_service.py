"""Calendar service for managing user schedules and events."""

import uuid
from datetime import date, datetime, time, timedelta
from typing import Sequence

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.base import ScheduleType
from app.models.calendar_event import CalendarEvent
from app.models.user_schedule_config import UserScheduleConfig
from app.services.rrule_helper import (
    RRuleValidationError,
    get_occurrences,
    get_recurrence_end,
    validate_rrule,
)


def get_schedule_config(db: Session, user_id: uuid.UUID) -> UserScheduleConfig | None:
    """Get user's schedule configuration."""
    return db.scalar(
        select(UserScheduleConfig).where(UserScheduleConfig.user_id == user_id)
    )


def create_schedule_config(
    db: Session,
    user_id: uuid.UUID,
    timezone: str = "UTC",
    work_days: list[int] | None = None,
    work_start_time: time | None = None,
    work_end_time: time | None = None,
    day_overrides: dict | None = None,
) -> UserScheduleConfig:
    """Create schedule configuration for a user."""
    config = UserScheduleConfig(
        id=uuid.uuid4(),
        user_id=user_id,
        timezone=timezone,
        work_days=work_days if work_days is not None else [0, 1, 2, 3, 4],
        work_start_time=work_start_time or time(9, 0),
        work_end_time=work_end_time or time(17, 0),
        day_overrides=day_overrides,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def update_schedule_config(
    db: Session,
    config: UserScheduleConfig,
    **kwargs,
) -> UserScheduleConfig:
    """Update schedule configuration."""
    for key, value in kwargs.items():
        if hasattr(config, key) and value is not None:
            setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config


def get_or_create_schedule_config(
    db: Session,
    user_id: uuid.UUID,
) -> UserScheduleConfig:
    """Get existing config or create with defaults."""
    config = get_schedule_config(db, user_id)
    if config is None:
        config = create_schedule_config(db, user_id)
    return config


def create_event(
    db: Session,
    user_id: uuid.UUID,
    schedule_type: ScheduleType,
    title: str,
    start_datetime: datetime,
    end_datetime: datetime,
    timezone: str = "UTC",
    description: str | None = None,
    all_day: bool = False,
    rrule: str | None = None,
    external_id: str | None = None,
) -> CalendarEvent:
    """Create a calendar event."""
    is_recurring = bool(rrule)
    recurrence_end = None

    if rrule:
        validate_rrule(rrule)
        recurrence_end = get_recurrence_end(rrule, start_datetime)

    event = CalendarEvent(
        id=uuid.uuid4(),
        user_id=user_id,
        schedule_type=schedule_type,
        title=title,
        description=description,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        all_day=all_day,
        timezone=timezone,
        is_recurring=is_recurring,
        rrule=rrule,
        recurrence_end=recurrence_end,
        external_id=external_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_event(db: Session, event_id: uuid.UUID) -> CalendarEvent | None:
    """Get a single event by ID."""
    return db.get(CalendarEvent, event_id)


def update_event(
    db: Session,
    event: CalendarEvent,
    **kwargs,
) -> CalendarEvent:
    """Update an event."""
    if 'rrule' in kwargs:
        new_rrule = kwargs['rrule']
        if new_rrule:
            validate_rrule(new_rrule)
            kwargs['is_recurring'] = True
            kwargs['recurrence_end'] = get_recurrence_end(new_rrule, event.start_datetime)
        else:
            kwargs['is_recurring'] = False
            kwargs['recurrence_end'] = None

    for key, value in kwargs.items():
        if hasattr(event, key):
            setattr(event, key, value)

    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, event: CalendarEvent) -> None:
    """Delete an event."""
    db.delete(event)
    db.commit()


def list_events(
    db: Session,
    user_id: uuid.UUID,
    start_date: date,
    end_date: date,
    schedule_types: list[ScheduleType] | None = None,
) -> Sequence[CalendarEvent]:
    """List events within a date range.

    Includes:
    - One-time events in the range
    - Recurring events that may have occurrences in the range
    """
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    conditions = [
        CalendarEvent.user_id == user_id,
        or_(
            # One-time events in range
            and_(
                CalendarEvent.is_recurring == False,
                CalendarEvent.start_datetime >= start_dt,
                CalendarEvent.start_datetime <= end_dt,
            ),
            # Recurring events that started before window end
            # and either have no end or end after window start
            and_(
                CalendarEvent.is_recurring == True,
                CalendarEvent.start_datetime <= end_dt,
                or_(
                    CalendarEvent.recurrence_end == None,
                    CalendarEvent.recurrence_end >= start_date,
                ),
            ),
        ),
    ]

    if schedule_types:
        conditions.append(CalendarEvent.schedule_type.in_(schedule_types))

    return db.scalars(
        select(CalendarEvent).where(*conditions)
    ).all()


def add_exception_date(
    db: Session,
    event: CalendarEvent,
    exception_date: date,
) -> CalendarEvent:
    """Skip a specific occurrence of a recurring event."""
    if not event.is_recurring:
        raise ValueError("Cannot add exception to non-recurring event")

    exdates = list(event.exdates) if event.exdates else []
    date_str = exception_date.isoformat()
    if date_str not in exdates:
        exdates.append(date_str)
        event.exdates = exdates
        db.commit()
        db.refresh(event)

    return event


def expand_recurring_event(
    event: CalendarEvent,
    window_start: date,
    window_end: date,
) -> list[tuple[datetime, datetime]]:
    """Expand a recurring event to concrete occurrences.

    Args:
        event: The recurring calendar event
        window_start: Start of query window
        window_end: End of query window

    Returns:
        List of (start_datetime, end_datetime) tuples
    """
    if not event.is_recurring or not event.rrule:
        # For non-recurring, return the single occurrence if in range
        if event.start_datetime.date() >= window_start and event.start_datetime.date() <= window_end:
            return [(event.start_datetime, event.end_datetime)]
        return []

    duration = event.end_datetime - event.start_datetime
    window_start_dt = datetime.combine(window_start, time.min)
    window_end_dt = datetime.combine(window_end, time.max)

    exdates = None
    if event.exdates:
        exdates = [date.fromisoformat(d) for d in event.exdates]

    occurrences = get_occurrences(
        event.rrule,
        event.start_datetime,
        window_start_dt,
        window_end_dt,
        exdates,
    )

    return [(occ, occ + duration) for occ in occurrences]
