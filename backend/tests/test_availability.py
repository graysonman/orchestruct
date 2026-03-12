"""Tests for availability computation service."""

import pytest
from datetime import date, time
from unittest.mock import MagicMock

from app.models.base import ScheduleType
from app.models.calendar_event import CalendarEvent
from app.models.user_schedule_config import UserScheduleConfig
from app.services.availability_service import (
    DayAvailability,
    TimeSlot,
    compute_free_slots,
    compute_work_hours_for_day,
    get_busy_slots,
)


class TestComputeWorkHoursForDay:
    def test_work_day(self):
        config = MagicMock(spec=UserScheduleConfig)
        config.work_days = [0, 1, 2, 3, 4]  # Mon-Fri
        config.work_start_time = time(9, 0)
        config.work_end_time = time(17, 0)
        config.day_overrides = None

        # Monday (weekday 0)
        result = compute_work_hours_for_day(config, date(2026, 3, 2))
        assert result is not None
        assert result.start == time(9, 0)
        assert result.end == time(17, 0)

    def test_non_work_day(self):
        config = MagicMock(spec=UserScheduleConfig)
        config.work_days = [0, 1, 2, 3, 4]  # Mon-Fri
        config.day_overrides = None

        # Saturday (weekday 5)
        result = compute_work_hours_for_day(config, date(2026, 3, 7))
        assert result is None

    def test_day_override(self):
        config = MagicMock(spec=UserScheduleConfig)
        config.work_days = [0, 1, 2, 3, 4]
        config.work_start_time = time(9, 0)
        config.work_end_time = time(17, 0)
        config.day_overrides = {
            "0": {"start": "08:00", "end": "16:00"}  # Monday override
        }

        # Monday (weekday 0)
        result = compute_work_hours_for_day(config, date(2026, 3, 2))
        assert result is not None
        assert result.start == time(8, 0)
        assert result.end == time(16, 0)


class TestComputeFreeSlots:
    def test_no_busy_slots(self):
        work_hours = TimeSlot(start=time(9, 0), end=time(17, 0))
        free_slots = compute_free_slots(work_hours, [])

        assert len(free_slots) == 1
        assert free_slots[0].start == time(9, 0)
        assert free_slots[0].end == time(17, 0)

    def test_single_busy_slot_middle(self):
        work_hours = TimeSlot(start=time(9, 0), end=time(17, 0))
        busy_slots = [TimeSlot(start=time(12, 0), end=time(13, 0))]

        free_slots = compute_free_slots(work_hours, busy_slots)

        assert len(free_slots) == 2
        assert free_slots[0].start == time(9, 0)
        assert free_slots[0].end == time(12, 0)
        assert free_slots[1].start == time(13, 0)
        assert free_slots[1].end == time(17, 0)

    def test_busy_at_start(self):
        work_hours = TimeSlot(start=time(9, 0), end=time(17, 0))
        busy_slots = [TimeSlot(start=time(9, 0), end=time(10, 0))]

        free_slots = compute_free_slots(work_hours, busy_slots)

        assert len(free_slots) == 1
        assert free_slots[0].start == time(10, 0)
        assert free_slots[0].end == time(17, 0)

    def test_busy_at_end(self):
        work_hours = TimeSlot(start=time(9, 0), end=time(17, 0))
        busy_slots = [TimeSlot(start=time(16, 0), end=time(17, 0))]

        free_slots = compute_free_slots(work_hours, busy_slots)

        assert len(free_slots) == 1
        assert free_slots[0].start == time(9, 0)
        assert free_slots[0].end == time(16, 0)

    def test_multiple_busy_slots(self):
        work_hours = TimeSlot(start=time(9, 0), end=time(17, 0))
        busy_slots = [
            TimeSlot(start=time(10, 0), end=time(11, 0)),
            TimeSlot(start=time(14, 0), end=time(15, 0)),
        ]

        free_slots = compute_free_slots(work_hours, busy_slots)

        assert len(free_slots) == 3
        assert free_slots[0] == TimeSlot(start=time(9, 0), end=time(10, 0))
        assert free_slots[1] == TimeSlot(start=time(11, 0), end=time(14, 0))
        assert free_slots[2] == TimeSlot(start=time(15, 0), end=time(17, 0))

    def test_fully_busy(self):
        work_hours = TimeSlot(start=time(9, 0), end=time(17, 0))
        busy_slots = [TimeSlot(start=time(9, 0), end=time(17, 0))]

        free_slots = compute_free_slots(work_hours, busy_slots)
        assert len(free_slots) == 0

    def test_busy_outside_work_hours(self):
        work_hours = TimeSlot(start=time(9, 0), end=time(17, 0))
        busy_slots = [
            TimeSlot(start=time(7, 0), end=time(8, 0)),  # Before work
            TimeSlot(start=time(18, 0), end=time(19, 0)),  # After work
        ]

        free_slots = compute_free_slots(work_hours, busy_slots)

        assert len(free_slots) == 1
        assert free_slots[0].start == time(9, 0)
        assert free_slots[0].end == time(17, 0)

    def test_busy_partially_overlapping_start(self):
        work_hours = TimeSlot(start=time(9, 0), end=time(17, 0))
        busy_slots = [TimeSlot(start=time(8, 0), end=time(10, 0))]

        free_slots = compute_free_slots(work_hours, busy_slots)

        assert len(free_slots) == 1
        assert free_slots[0].start == time(10, 0)
        assert free_slots[0].end == time(17, 0)


class TestTimeSlot:
    def test_equality(self):
        slot1 = TimeSlot(start=time(9, 0), end=time(10, 0))
        slot2 = TimeSlot(start=time(9, 0), end=time(10, 0))
        assert slot1 == slot2

    def test_inequality(self):
        slot1 = TimeSlot(start=time(9, 0), end=time(10, 0))
        slot2 = TimeSlot(start=time(9, 0), end=time(11, 0))
        assert slot1 != slot2


class TestDayAvailability:
    def test_work_day_with_availability(self):
        day = DayAvailability(
            date=date(2026, 3, 2),
            work_hours=TimeSlot(start=time(9, 0), end=time(17, 0)),
            busy_slots=[TimeSlot(start=time(12, 0), end=time(13, 0))],
            free_slots=[
                TimeSlot(start=time(9, 0), end=time(12, 0)),
                TimeSlot(start=time(13, 0), end=time(17, 0)),
            ],
        )
        assert day.work_hours is not None
        assert len(day.busy_slots) == 1
        assert len(day.free_slots) == 2

    def test_non_work_day(self):
        day = DayAvailability(
            date=date(2026, 3, 7),
            work_hours=None,
            busy_slots=[],
            free_slots=[],
        )
        assert day.work_hours is None
        assert len(day.free_slots) == 0
