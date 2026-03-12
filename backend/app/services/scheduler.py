"""Task scheduler for placing tasks into available time slots."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from app.services.availability_service import DayAvailability, TimeSlot


@dataclass
class ScheduledTask:
    task_id: str
    title: str
    estimated_minutes: int
    difficulty: int          # 1-5
    dislike_score: int       # 0-5
    due_date: date | None
    priority_weight: float   # inherited from parent goal


@dataclass
class ScheduledItem:
    task_id: str
    scheduled_date: date
    start_time: time
    end_time: time
    risk_score: float
    rationale: dict[str, Any]


# Default fallback values (used when no user config)
DEFAULT_WORK_START = time(9, 0)
DEFAULT_WORK_END = time(17, 0)
DEFAULT_WORK_DAYS = {0, 1, 2, 3, 4}  # Mon-Fri


def _minutes_between(t1: time, t2: time) -> int:
    d = date.today()
    return int((datetime.combine(d, t2) - datetime.combine(d, t1)).total_seconds() / 60)


def _add_minutes(t: time, minutes: int) -> time:
    return (datetime.combine(date.today(), t) + timedelta(minutes=minutes)).time()


def _score(task: ScheduledTask, today: date) -> float:
    days_until_due = (task.due_date - today).days if task.due_date else 30
    urgency = task.priority_weight / max(days_until_due, 1)
    urgency += task.difficulty + task.dislike_score
    return urgency


def build_availability_grid_default(
    window_start: date,
    window_end: date,
    work_days: set[int] | None = None,
) -> list[date]:
    """Return a list of working days in the window (fallback for no config)."""
    if work_days is None:
        work_days = DEFAULT_WORK_DAYS

    days = []
    current = window_start
    while current <= window_end:
        if current.weekday() in work_days:
            days.append(current)
        current += timedelta(days=1)
    return days


def _find_slot_in_free_time(
    free_slots: list[TimeSlot],
    cursor: time,
    duration_minutes: int,
) -> tuple[time, time] | None:
    """Find an available slot within free time periods.

    Args:
        free_slots: Available free time slots (e.g., [9:00-10:00, 11:00-14:00])
        cursor: Current position in the day (tasks already scheduled before this)
        duration_minutes: Required task duration (e.g., 60 for a 1-hour task)

    Returns:
        (start_time, end_time) tuple if slot found, None otherwise

    Example:
        free_slots: [9:00-10:00, 11:00-14:00, 15:00-17:00]
        cursor: 11:30
        duration_minutes: 90

        First slot (9:00-10:00): cursor is past it, skip
        Second slot (11:00-14:00): effective_start = max(11:30, 11:00) = 11:30
            available = 14:00 - 11:30 = 150 mins, need 90 → fits!
        Returns: (11:30, 13:00)
    """
    for slot in free_slots:
        start = max(cursor, slot.start)
        if _minutes_between(start, slot.end) >= duration_minutes:
            return (start, _add_minutes(start, duration_minutes))
    return None

def _place_tasks_with_availability(
    tasks: list[ScheduledTask],
    availability: list[DayAvailability],
) -> list[ScheduledItem]:
    """Place tasks respecting availability from calendar."""
    scheduled = []
    sorted_tasks = sorted(tasks, key=lambda t: _score(t, date.today()), reverse=True)

    day_cursors: dict[date, time] = {}
    for day in availability:
        if day.work_hours and day.free_slots:
            day_cursors[day.date] = day.free_slots[0].start

    for task in sorted_tasks:
        if not task.estimated_minutes:
            continue

        for day in availability:
            if day.work_hours is None or not day.free_slots:
                continue

            cursor = day_cursors.get(day.date, day.free_slots[0].start)
            slot = _find_slot_in_free_time(
                day.free_slots,
                cursor,
                task.estimated_minutes,
            )

            if slot:
                start_time, end_time = slot
                scheduled.append(ScheduledItem(
                    task_id=task.task_id,
                    scheduled_date=day.date,
                    start_time=start_time,
                    end_time=end_time,
                    risk_score=task.difficulty * task.dislike_score / 25.0,
                    rationale={
                        "score": _score(task, date.today()),
                        "placed_on": str(day.date),
                        "reason": "greedy",
                    },
                ))
                day_cursors[day.date] = end_time
                break

    return scheduled


def _place_tasks_default(
    tasks: list[ScheduledTask],
    grid: list[date],
    work_start: time = DEFAULT_WORK_START,
    work_end: time = DEFAULT_WORK_END,
) -> list[ScheduledItem]:
    """Place tasks using default work hours (no calendar integration)."""
    scheduled = []
    cursors = {day: work_start for day in grid}
    sorted_tasks = sorted(tasks, key=lambda t: _score(t, date.today()), reverse=True)

    for task in sorted_tasks:
        if not task.estimated_minutes:
            continue
        for day in grid:
            if _minutes_between(cursors[day], work_end) >= task.estimated_minutes:
                scheduled.append(ScheduledItem(
                    task_id=task.task_id,
                    scheduled_date=day,
                    start_time=cursors[day],
                    end_time=_add_minutes(cursors[day], task.estimated_minutes),
                    risk_score=task.difficulty * task.dislike_score / 25.0,
                    rationale={
                        "score": _score(task, date.today()),
                        "placed_on": str(day),
                        "reason": "greedy",
                    },
                ))
                cursors[day] = _add_minutes(cursors[day], task.estimated_minutes)
                break

    return scheduled


def compute_risk_metrics(items: list[ScheduledItem], tasks: list[ScheduledTask]) -> dict:
    """Summarise risk across the full schedule."""
    if not items:
        return {"scheduled": 0, "unscheduled": len(tasks), "avg_risk": 0.0}

    scheduled_ids = {str(i.task_id) for i in items}
    unscheduled = sum(1 for t in tasks if str(t.task_id) not in scheduled_ids)
    avg_risk = sum(i.risk_score for i in items) / len(items)

    return {
        "scheduled": len(items),
        "unscheduled": unscheduled,
        "avg_risk": round(avg_risk, 3),
    }


def run(
    tasks: list[ScheduledTask],
    window_start: date,
    window_end: date,
    availability: list[DayAvailability] | None = None,
) -> tuple[list[ScheduledItem], dict]:
    """Entry point. Returns (scheduled_items, risk_summary).

    Args:
        tasks: Tasks to schedule
        window_start: Start of planning window
        window_end: End of planning window
        availability: Optional availability grid from calendar service.
                     If None, uses default work hours.
    """
    if not tasks:
        return [], {"scheduled": 0, "unscheduled": 0, "avg_risk": 0.0}

    if availability:
        items = _place_tasks_with_availability(tasks, availability)
    else:
        grid = build_availability_grid_default(window_start, window_end)
        items = _place_tasks_default(tasks, grid)

    risk_summary = compute_risk_metrics(items, tasks)
    return items, risk_summary
