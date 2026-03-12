"""Tests for RRULE parsing and expansion utilities."""

import pytest
from datetime import date, datetime, time

from app.services.rrule_helper import (
    RRuleValidationError,
    get_occurrences,
    get_recurrence_end,
    iter_occurrences,
    parse_rrule,
    validate_rrule,
)


class TestValidateRRule:
    def test_valid_daily(self):
        assert validate_rrule("FREQ=DAILY") is True

    def test_valid_weekly_with_byday(self):
        assert validate_rrule("FREQ=WEEKLY;BYDAY=MO,WE,FR") is True

    def test_valid_monthly_bymonthday(self):
        assert validate_rrule("FREQ=MONTHLY;BYMONTHDAY=15") is True

    def test_valid_with_count(self):
        assert validate_rrule("FREQ=DAILY;COUNT=10") is True

    def test_valid_with_until(self):
        assert validate_rrule("FREQ=WEEKLY;UNTIL=20261231T235959Z") is True

    def test_valid_with_interval(self):
        assert validate_rrule("FREQ=DAILY;INTERVAL=2") is True

    def test_invalid_empty(self):
        with pytest.raises(RRuleValidationError, match="cannot be empty"):
            validate_rrule("")

    def test_invalid_syntax(self):
        with pytest.raises(RRuleValidationError):
            validate_rrule("INVALID=RRULE")


class TestParseRRule:
    def test_parse_daily(self):
        dtstart = datetime(2026, 3, 1, 9, 0)
        rule = parse_rrule("FREQ=DAILY", dtstart)
        assert rule is not None

    def test_parse_weekly_byday(self):
        dtstart = datetime(2026, 3, 2, 9, 0)  # Monday
        rule = parse_rrule("FREQ=WEEKLY;BYDAY=MO,WE,FR", dtstart)
        occurrences = list(rule.between(
            datetime(2026, 3, 2),
            datetime(2026, 3, 8),
            inc=True,
        ))
        # Should get Mon, Wed, Fri
        assert len(occurrences) == 3
        assert occurrences[0].weekday() == 0  # Monday
        assert occurrences[1].weekday() == 2  # Wednesday
        assert occurrences[2].weekday() == 4  # Friday


class TestGetOccurrences:
    def test_daily_in_range(self):
        dtstart = datetime(2026, 3, 1, 9, 0)
        occurrences = get_occurrences(
            "FREQ=DAILY",
            dtstart,
            datetime(2026, 3, 1),
            datetime(2026, 3, 5, 23, 59),  # Include full day
        )
        assert len(occurrences) == 5

    def test_weekly_in_range(self):
        dtstart = datetime(2026, 3, 2, 9, 0)  # Monday
        occurrences = get_occurrences(
            "FREQ=WEEKLY;BYDAY=MO",
            dtstart,
            datetime(2026, 3, 1),
            datetime(2026, 3, 31, 23, 59),
        )
        # Mondays in March 2026: 2, 9, 16, 23, 30
        assert len(occurrences) == 5

    def test_with_exdates(self):
        dtstart = datetime(2026, 3, 1, 9, 0)
        occurrences = get_occurrences(
            "FREQ=DAILY",
            dtstart,
            datetime(2026, 3, 1),
            datetime(2026, 3, 5, 23, 59),
            exdates=[date(2026, 3, 3)],
        )
        # 5 days minus 1 excluded
        assert len(occurrences) == 4
        assert datetime(2026, 3, 3, 9, 0) not in occurrences

    def test_nth_weekday(self):
        dtstart = datetime(2026, 3, 10, 9, 0)  # 2nd Tuesday
        occurrences = get_occurrences(
            "FREQ=MONTHLY;BYDAY=2TU",
            dtstart,
            datetime(2026, 3, 1),
            datetime(2026, 5, 31),
        )
        # 2nd Tuesday of March, April, May
        assert len(occurrences) == 3
        # All should be Tuesdays
        for occ in occurrences:
            assert occ.weekday() == 1


class TestGetRecurrenceEnd:
    def test_with_until(self):
        from datetime import timezone
        dtstart = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
        end = get_recurrence_end(
            "FREQ=DAILY;UNTIL=20261231T235959Z",
            dtstart,
        )
        assert end == date(2026, 12, 31)

    def test_with_count(self):
        dtstart = datetime(2026, 3, 1, 9, 0)
        end = get_recurrence_end(
            "FREQ=DAILY;COUNT=10",
            dtstart,
        )
        # 10 days from March 1
        assert end == date(2026, 3, 10)

    def test_infinite(self):
        dtstart = datetime(2026, 3, 1, 9, 0)
        end = get_recurrence_end("FREQ=DAILY", dtstart)
        assert end is None


class TestIterOccurrences:
    def test_lazy_iteration(self):
        dtstart = datetime(2026, 3, 1, 9, 0)
        iterator = iter_occurrences(
            "FREQ=DAILY",
            dtstart,
            datetime(2026, 3, 1),
            datetime(2026, 3, 5, 23, 59),
        )
        first = next(iterator)
        assert first == datetime(2026, 3, 1, 9, 0)

    def test_with_exdates(self):
        dtstart = datetime(2026, 3, 1, 9, 0)
        occurrences = list(iter_occurrences(
            "FREQ=DAILY",
            dtstart,
            datetime(2026, 3, 1),
            datetime(2026, 3, 5, 23, 59),
            exdates=[date(2026, 3, 2), date(2026, 3, 4)],
        ))
        # 5 days minus 2 excluded
        assert len(occurrences) == 3


class TestRealWorldPatterns:
    """Test RRULE patterns from the plan spec."""

    def test_every_weekday(self):
        dtstart = datetime(2026, 3, 2, 9, 0)  # Monday
        occurrences = get_occurrences(
            "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
            dtstart,
            datetime(2026, 3, 2),
            datetime(2026, 3, 8),
        )
        # Mon-Fri = 5 days
        assert len(occurrences) == 5

    def test_every_other_day(self):
        dtstart = datetime(2026, 3, 1, 9, 0)
        occurrences = get_occurrences(
            "FREQ=DAILY;INTERVAL=2",
            dtstart,
            datetime(2026, 3, 1),
            datetime(2026, 3, 10),
        )
        # Days 1, 3, 5, 7, 9 = 5 occurrences
        assert len(occurrences) == 5

    def test_15th_of_month(self):
        dtstart = datetime(2026, 3, 15, 9, 0)
        occurrences = get_occurrences(
            "FREQ=MONTHLY;BYMONTHDAY=15",
            dtstart,
            datetime(2026, 1, 1),
            datetime(2026, 6, 30),
        )
        # March, April, May, June = 4 (starts from dtstart)
        assert len(occurrences) == 4

    def test_last_friday(self):
        dtstart = datetime(2026, 3, 27, 9, 0)  # Last Friday of March
        occurrences = get_occurrences(
            "FREQ=MONTHLY;BYDAY=-1FR",
            dtstart,
            datetime(2026, 3, 1),
            datetime(2026, 5, 31),
        )
        # Last Fridays: Mar 27, Apr 24, May 29
        assert len(occurrences) == 3
        for occ in occurrences:
            assert occ.weekday() == 4  # Friday
