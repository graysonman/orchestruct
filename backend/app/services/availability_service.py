"""Availability computation service for the planning engine.

Computes free/busy slots by combining work hours with calendar events.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Sequence

from sqlalchemy.orm import Session

from app.models.base import ScheduleType
from app.models.calendar_event import CalendarEvent
from app.models.user_schedule_config import UserScheduleConfig
from app.services import calendar_service


@dataclass
class TimeSlot:
    """A time slot with start and end times."""
    start: time
    end: time


@dataclass
class DayAvailability:
    """Availability for a single day."""
    date: date
    work_hours: TimeSlot | None  # None = not a work day
    busy_slots: list[TimeSlot]
    free_slots: list[TimeSlot]


def compute_work_hours_for_day(
    config: UserScheduleConfig,
    day: date,
) -> TimeSlot | None:
    """Get work hours for a specific day, including overrides.

    Args:
        config: User's schedule configuration
        day: The date to get work hours for

    Returns:
        TimeSlot with work hours, or None if not a work day
    """
    weekday = day.weekday()

    if weekday not in config.work_days:
        return None

    if config.day_overrides:
        override_key = str(weekday)
        if override_key in config.day_overrides:
            override = config.day_overrides[override_key]
            start = time.fromisoformat(override["start"])
            end = time.fromisoformat(override["end"])
            return TimeSlot(start=start, end=end)

    return TimeSlot(start=config.work_start_time, end=config.work_end_time)


def get_busy_slots(
    events: Sequence[CalendarEvent],
    day: date,
) -> list[TimeSlot]:
    """Get all busy time slots for a day from calendar events.

    Args:
        events: Calendar events that may affect this day
        day: The date to compute busy slots for

    Returns:
        List of busy TimeSlots, sorted by start time
    """
    busy_slots = []

    for event in events:
        if event.schedule_type == ScheduleType.WORK:
            continue

        occurrences = calendar_service.expand_recurring_event(event, day, day)

        for start_dt, end_dt in occurrences:
            if start_dt.date() != day:
                continue

            if event.all_day:
                busy_slots.append(TimeSlot(start=time.min, end=time.max))
            else:
                busy_slots.append(TimeSlot(start=start_dt.time(), end=end_dt.time()))

    busy_slots.sort(key=lambda s: s.start)
    return _merge_overlapping_slots(busy_slots)


def _merge_overlapping_slots(slots: list[TimeSlot]) -> list[TimeSlot]:
    """Merge overlapping time slots."""
    if not slots:
        return []

    merged = [slots[0]]
    for current in slots[1:]:
        last = merged[-1]
        if current.start <= last.end:
            merged[-1] = TimeSlot(start=last.start, end=max(last.end, current.end))
        else:
            merged.append(current)

    return merged


def _time_to_minutes(t: time) -> int:
    """Convert time to minutes since midnight."""
    return t.hour * 60 + t.minute


def _minutes_to_time(minutes: int) -> time:
    """Convert minutes since midnight to time."""
    return time(hour=minutes // 60, minute=minutes % 60)


def compute_free_slots(
    work_hours: TimeSlot,
    busy_slots: list[TimeSlot],
) -> list[TimeSlot]:
    """Subtract busy slots from work hours to get free slots.

    Args:
        work_hours: The work hours TimeSlot (e.g., 9:00-17:00)
        busy_slots: List of busy TimeSlots (already merged, sorted by start)

    Returns:
        List of free TimeSlots

    Example:
        work_hours: 9:00-17:00
        busy_slots: [10:00-11:00, 14:00-15:00]
        returns:    [9:00-10:00, 11:00-14:00, 15:00-17:00]
    """
    if not busy_slots:
        return [work_hours]
    
    free_slots = []
    cursor = work_hours.start
    for slot in busy_slots:
        if slot.start > work_hours.end:
            continue
        if slot.end <= work_hours.start:
            continue
        if cursor < slot.start:
            free_slots.append(TimeSlot(start=cursor, end=slot.start))
        cursor = slot.end
    
    if cursor < work_hours.end:
        free_slots.append(TimeSlot(start=cursor, end=work_hours.end))

    return free_slots


def build_availability_grid(
    db: Session,
    user_id: uuid.UUID,
    window_start: date,
    window_end: date,
) -> list[DayAvailability]:
    """Build full availability grid for a planning window.

    Args:
        db: Database session
        user_id: User's ID
        window_start: Start of planning window
        window_end: End of planning window

    Returns:
        List of DayAvailability objects
    """
    config = calendar_service.get_or_create_schedule_config(db, user_id)

    events = calendar_service.list_events(
        db,
        user_id,
        window_start,
        window_end,
        schedule_types=[ScheduleType.PERSONAL, ScheduleType.BLOCKED],
    )

    grid = []
    current = window_start

    while current <= window_end:
        work_hours = compute_work_hours_for_day(config, current)

        if work_hours is None:
            grid.append(DayAvailability(
                date=current,
                work_hours=None,
                busy_slots=[],
                free_slots=[],
            ))
        else:
            busy_slots = get_busy_slots(events, current)
            free_slots = compute_free_slots(work_hours, busy_slots)

            grid.append(DayAvailability(
                date=current,
                work_hours=work_hours,
                busy_slots=busy_slots,
                free_slots=free_slots,
            ))

        current += timedelta(days=1)

    return grid


def get_availability_summary(
    grid: list[DayAvailability],
) -> dict:
    """Compute summary statistics for an availability grid.

    Args:
        grid: List of DayAvailability objects

    Returns:
        Summary dict with total hours, work days, etc.
    """
    work_days = 0
    total_work_minutes = 0
    total_busy_minutes = 0
    total_free_minutes = 0

    for day in grid:
        if day.work_hours is None:
            continue

        work_days += 1
        work_minutes = _time_to_minutes(day.work_hours.end) - _time_to_minutes(day.work_hours.start)
        total_work_minutes += work_minutes

        for slot in day.busy_slots:
            slot_minutes = _time_to_minutes(slot.end) - _time_to_minutes(slot.start)
            total_busy_minutes += slot_minutes

        for slot in day.free_slots:
            slot_minutes = _time_to_minutes(slot.end) - _time_to_minutes(slot.start)
            total_free_minutes += slot_minutes

    return {
        "work_days": work_days,
        "total_work_hours": round(total_work_minutes / 60, 1),
        "total_busy_hours": round(total_busy_minutes / 60, 1),
        "total_free_hours": round(total_free_minutes / 60, 1),
        "utilization_percent": round(total_busy_minutes / total_work_minutes * 100, 1) if total_work_minutes else 0,
    }
