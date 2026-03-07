from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any


@dataclass
class ScheduledTask:
    task_id: str
    title: str
    estimated_minutes: int
    difficulty: int          # 1–5
    dislike_score: int       # 0–5
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

# TODO: load from user preferences
WORK_START = time(9, 0)
WORK_END = time(17, 0)
WORK_DAYS = {0, 1, 2, 3, 4}  # Mon–Fri


def build_availability_grid(window_start: date, window_end: date) -> list[date]:
    """Return a list of working days (Mon–Fri) in the window."""
    days = []
    current = window_start
    while current <= window_end:
        if current.weekday() in WORK_DAYS:
            days.append(current)
        current += timedelta(days=1)
    return days


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


def _place_tasks(
    tasks: list[ScheduledTask],
    grid: list[date],
) -> list[ScheduledItem]:
    scheduled = []
    cursors = {day: WORK_START for day in grid}
    sorted_tasks = sorted(tasks, key=lambda t: _score(t, date.today()), reverse=True)

    for task in sorted_tasks:
        if not task.estimated_minutes:
                continue
        for day in grid:
            if _minutes_between(cursors[day], WORK_END) >= task.estimated_minutes:
                scheduled.append(ScheduledItem(
                    task_id=task.task_id,
                    scheduled_date=day,
                    start_time=cursors[day],
                    end_time=_add_minutes(cursors[day], task.estimated_minutes),
                    risk_score=task.difficulty * task.dislike_score / 25.0,
                    rationale = {"score": _score(task, date.today()), "placed_on": str(day), "reason": "greedy"}
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
) -> tuple[list[ScheduledItem], dict]:
    """Entry point. Returns (scheduled_items, risk_summary)."""
    if not tasks:
        return [], {"scheduled": 0, "unscheduled": 0, "avg_risk": 0.0}

    grid = build_availability_grid(window_start, window_end)
    items = _place_tasks(tasks, grid)
    risk_summary = compute_risk_metrics(items, tasks)
    return items, risk_summary
