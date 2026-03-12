"""RRULE parsing and expansion utilities using python-dateutil.

Provides iCalendar RFC 5545 compliant recurrence rule support.
"""

from datetime import date, datetime, time, timezone
from typing import Iterator

from dateutil import rrule
from dateutil.rrule import rrulestr


class RRuleValidationError(ValueError):
    """Raised when an RRULE string is invalid."""
    pass


def validate_rrule(rrule_string: str) -> bool:
    """Validate an RRULE string syntax.

    Args:
        rrule_string: iCalendar RRULE string (e.g., "FREQ=WEEKLY;BYDAY=MO,WE,FR")

    Returns:
        True if valid

    Raises:
        RRuleValidationError: If the RRULE is invalid
    """
    if not rrule_string:
        raise RRuleValidationError("RRULE string cannot be empty")

    try:
        dummy_start = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
        rrulestr(rrule_string, dtstart=dummy_start)
        return True
    except (ValueError, TypeError) as e:
        raise RRuleValidationError(f"Invalid RRULE: {e}") from e


def parse_rrule(rrule_string: str, dtstart: datetime) -> rrule.rrule:
    """Parse an RRULE string into a dateutil rrule object.

    Args:
        rrule_string: iCalendar RRULE string
        dtstart: The start datetime for the recurrence

    Returns:
        Parsed rrule object
    """
    return rrulestr(rrule_string, dtstart=dtstart)


def get_occurrences(
    rrule_string: str,
    dtstart: datetime,
    window_start: datetime,
    window_end: datetime,
    exdates: list[date] | None = None
) -> list[datetime]:
    """Expand an RRULE to concrete occurrences within a time window.

    Args:
        rrule_string: iCalendar RRULE string
        dtstart: Event start datetime
        window_start: Start of query window
        window_end: End of query window
        exdates: List of dates to exclude

    Returns:
        List of occurrence datetimes
    """
    rule = parse_rrule(rrule_string, dtstart)
    occurrences = rule.between(window_start, window_end, inc=True)

    if not exdates:
        return list(occurrences)

    exdate_set = set(exdates)
    return [occ for occ in occurrences if occ.date() not in exdate_set]


def get_recurrence_end(rrule_string: str, dtstart: datetime) -> date | None:
    """Extract the end date from an RRULE (UNTIL or COUNT-based).

    Args:
        rrule_string: iCalendar RRULE string
        dtstart: Event start datetime

    Returns:
        End date if determinable, None for infinite recurrence
    """
    rule = parse_rrule(rrule_string, dtstart)

    if hasattr(rule, '_until') and rule._until:
        until = rule._until
        return until.date() if isinstance(until, datetime) else until

    if hasattr(rule, '_count') and rule._count:
        try:
            occurrences = list(rule)
            if occurrences:
                last = occurrences[-1]
                return last.date() if isinstance(last, datetime) else last
        except Exception:
            pass

    return None


def iter_occurrences(
    rrule_string: str,
    dtstart: datetime,
    window_start: datetime,
    window_end: datetime,
    exdates: list[date] | None = None
) -> Iterator[datetime]:
    """Lazily iterate over occurrences (memory-efficient for large ranges).

    Args:
        rrule_string: iCalendar RRULE string
        dtstart: Event start datetime
        window_start: Start of query window
        window_end: End of query window
        exdates: List of dates to exclude

    Yields:
        Occurrence datetimes
    """
    rule = parse_rrule(rrule_string, dtstart)
    exdate_set = set(exdates) if exdates else set()

    for occ in rule.between(window_start, window_end, inc=True):
        if occ.date() not in exdate_set:
            yield occ
