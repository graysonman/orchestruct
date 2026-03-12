"""Task scheduler for placing tasks into available time slots."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from app.services.availability_service import DayAvailability, TimeSlot


class ValidationError(Exception):
    """Raised when planning input validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {', '.join(errors)}")


@dataclass
class ScheduledTask:
    task_id: str
    title: str
    estimated_minutes: int
    difficulty: int          # 1-5
    dislike_score: int       # 0-5
    due_date: date | None
    priority_weight: float   # inherited from parent goal
    goal_id: str | None = None  # For context switching analysis


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


def _compute_score_breakdown(task: ScheduledTask, today: date) -> dict[str, float]:
    """Break down the scheduling score into components."""
    days_until_due = (task.due_date - today).days if task.due_date else 30
    urgency_component = task.priority_weight / max(days_until_due, 1)
    return {
        "urgency": round(urgency_component, 2),
        "difficulty": float(task.difficulty),
        "dislike": float(task.dislike_score),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validation Functions
# ─────────────────────────────────────────────────────────────────────────────


def validate_planning_window(
    window_start: date,
    window_end: date,
    today: date | None = None,
) -> list[str]:
    """Validate the planning window.

    Rules:
        - window_start must be >= today
        - window_end must be >= window_start
        - Window must be 1-14 days

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    if today is None:
        today = date.today()

    if window_start < today:
        errors.append(f"Planning window cannot start in the past (starts {window_start}, today is {today})")

    if window_end < window_start:
        errors.append(f"Planning window end ({window_end}) must be >= start ({window_start})")

    window_days = (window_end - window_start).days + 1
    if window_days < 1:
        errors.append("Planning window must be at least 1 day")
    elif window_days > 14:
        errors.append(f"Planning window cannot exceed 14 days (requested {window_days} days)")

    return errors


def validate_tasks(tasks: list[ScheduledTask]) -> list[str]:
    """Validate task data.

    Rules:
        - estimated_minutes must be > 0
        - difficulty must be 1-5

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    for task in tasks:
        if task.estimated_minutes is None or task.estimated_minutes <= 0:
            errors.append(f"Task '{task.title}' has invalid estimated_minutes: {task.estimated_minutes}")

        if task.difficulty < 1 or task.difficulty > 5:
            errors.append(f"Task '{task.title}' has invalid difficulty: {task.difficulty} (must be 1-5)")

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# Risk Metric Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _compute_day_metrics(
    items: list[ScheduledItem],
    availability: list[DayAvailability] | None,
) -> dict[date, dict]:
    """Aggregate load per day.

    Returns dict mapping date -> {
        scheduled_minutes: int,
        available_minutes: int,
        load_percent: float,
        task_count: int,
    }
    """
    day_metrics: dict[date, dict] = defaultdict(lambda: {
        "scheduled_minutes": 0,
        "available_minutes": 480,
        "load_percent": 0.0,
        "task_count": 0,
    })

    if availability:
        for day in availability:
            if day.work_hours and day.free_slots:
                total_free = sum(
                    _minutes_between(slot.start, slot.end)
                    for slot in day.free_slots
                )
                day_metrics[day.date]["available_minutes"] = total_free

    for item in items:
        duration = _minutes_between(item.start_time, item.end_time)
        day_metrics[item.scheduled_date]["scheduled_minutes"] += duration
        day_metrics[item.scheduled_date]["task_count"] += 1

    for d, metrics in day_metrics.items():
        if metrics["available_minutes"] > 0:
            metrics["load_percent"] = round(
                metrics["scheduled_minutes"] / metrics["available_minutes"] * 100,
                1
            )

    return dict(day_metrics)


def _compute_context_switches(
    items: list[ScheduledItem],
    tasks: list[ScheduledTask],
) -> int:
    """Count goal-to-goal transitions in the schedule.

    A context switch occurs when consecutive tasks belong to different goals.
    """
    if len(items) < 2:
        return 0

    task_map = {t.task_id: t for t in tasks}
    sorted_items = sorted(items, key=lambda i: (i.scheduled_date, i.start_time))

    switches = 0
    prev_goal_id = None

    for item in sorted_items:
        task = task_map.get(item.task_id)
        current_goal_id = task.goal_id if task else None

        if prev_goal_id is not None and current_goal_id != prev_goal_id:
            switches += 1

        prev_goal_id = current_goal_id

    return switches


def _compute_burnout_likelihood(
    day_metrics: dict[date, dict],
    context_switches: int,
    unscheduled_count: int,
    total_tasks: int,
) -> float:
    """Compute composite burnout risk score (0-1).

    Factors:
        - High daily load (>80% on multiple days)
        - Frequent context switching
        - Many unscheduled tasks (overcommitment signal)
    """
    if not day_metrics:
        return 0.0

    overload_days = sum(1 for m in day_metrics.values() if m["load_percent"] > 80)
    overload_ratio = overload_days / max(len(day_metrics), 1)

    days_with_tasks = sum(1 for m in day_metrics.values() if m["task_count"] > 0)
    avg_switches_per_day = context_switches / max(days_with_tasks, 1)
    switch_factor = min(avg_switches_per_day / 4, 1.0)

    unscheduled_ratio = unscheduled_count / max(total_tasks, 1) if total_tasks else 0.0

    burnout = (
        0.4 * overload_ratio +
        0.3 * switch_factor +
        0.3 * unscheduled_ratio
    )

    return round(min(burnout, 1.0), 2)


def _generate_deadline_warnings(
    items: list[ScheduledItem],
    tasks: list[ScheduledTask],
) -> list[dict]:
    """Generate warnings for tasks scheduled close to or past deadlines."""
    warnings = []
    task_map = {t.task_id: t for t in tasks}
    scheduled_ids = {item.task_id for item in items}

    for item in items:
        task = task_map.get(item.task_id)
        if not task or not task.due_date:
            continue

        slack_days = (task.due_date - item.scheduled_date).days

        if slack_days < 0:
            warnings.append({
                "task_id": item.task_id,
                "task_title": task.title,
                "type": "past_deadline",
                "message": f"Scheduled {abs(slack_days)} day(s) after deadline",
                "severity": "high",
            })
        elif slack_days == 0:
            warnings.append({
                "task_id": item.task_id,
                "task_title": task.title,
                "type": "deadline_day",
                "message": "Scheduled on deadline day",
                "severity": "medium",
            })
        elif slack_days <= 2:
            warnings.append({
                "task_id": item.task_id,
                "task_title": task.title,
                "type": "deadline_close",
                "message": f"Only {slack_days} day(s) before deadline",
                "severity": "low",
            })

    for task in tasks:
        if task.task_id in scheduled_ids or not task.due_date:
            continue
        days_until = (task.due_date - date.today()).days
        if days_until <= 7:
            warnings.append({
                "task_id": task.task_id,
                "task_title": task.title,
                "type": "unscheduled_urgent",
                "message": f"Unscheduled task due in {days_until} day(s)",
                "severity": "high" if days_until <= 2 else "medium",
            })

    return warnings


def compute_schedule_quality_score(
    scheduled_count: int,
    total_tasks: int,
    avg_risk: float,
    deadline_slack_ratio: float,
    overload_ratio: float,
    context_switching_count: int,
    burnout_likelihood: float,
) -> int:
    """Compute overall schedule quality as a 0-100 score.

    Higher is better. This provides users with a single "at a glance" metric
    to understand if their generated plan is good.

    Args:
        scheduled_count: Number of tasks successfully scheduled
        total_tasks: Total number of tasks to schedule
        avg_risk: Average risk score (0-1, lower is better)
        deadline_slack_ratio: Average deadline buffer (higher is better, >1 is good)
        overload_ratio: Peak daily load (0-1, lower is better)
        context_switching_count: Goal transitions (lower is better)
        burnout_likelihood: Burnout risk (0-1, lower is better)

    Returns:
        Integer score 0-100 where:
        - 90-100: Excellent schedule
        - 70-89: Good schedule
        - 50-69: Acceptable but has issues
        - <50: Poor schedule, needs adjustment
    """
    if total_tasks == 0:
        return 100

    penalty = 0
    penalty += (1 - scheduled_count / total_tasks) * 30
    penalty += burnout_likelihood * 20
    penalty += min(overload_ratio, 1.0) * 20
    penalty += avg_risk * 15
    penalty += min(context_switching_count / max(scheduled_count, 1), 1.0) * 10
    penalty += -5 if deadline_slack_ratio > 1.5 else 0

    return max(0, min(100, int(100 - penalty)))


def _generate_recommendations(
    day_metrics: dict[date, dict],
    deadline_warnings: list[dict],
    context_switches: int,
    burnout_likelihood: float,
    unscheduled_count: int,
) -> list[str]:
    """Generate actionable recommendations based on risk analysis."""
    recommendations = []

    critical_days = [d for d, m in day_metrics.items() if m["load_percent"] > 90]
    if critical_days:
        recommendations.append(
            f"Consider redistributing tasks from overloaded days: {', '.join(str(d) for d in sorted(critical_days)[:3])}"
        )

    days_with_tasks = sum(1 for m in day_metrics.values() if m["task_count"] > 0)
    if days_with_tasks and context_switches / days_with_tasks > 2:
        recommendations.append(
            "High context switching detected. Consider grouping related tasks by goal."
        )

    high_severity = [w for w in deadline_warnings if w["severity"] == "high"]
    if high_severity:
        recommendations.append(
            f"{len(high_severity)} task(s) have critical deadline issues. Review and prioritize."
        )

    if burnout_likelihood > 0.6:
        recommendations.append(
            "Burnout risk is elevated. Consider extending the planning window or deferring low-priority tasks."
        )

    if unscheduled_count > 0:
        recommendations.append(
            f"{unscheduled_count} task(s) could not be scheduled. Extend the planning window or reduce task estimates."
        )

    return recommendations


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
    today = date.today()
    sorted_tasks = sorted(tasks, key=lambda t: _score(t, today), reverse=True)

    day_available: dict[date, int] = {}
    for day in availability:
        if day.work_hours and day.free_slots:
            day_available[day.date] = sum(
                _minutes_between(slot.start, slot.end) for slot in day.free_slots
            )

    day_cursors: dict[date, time] = {}
    day_scheduled_minutes: dict[date, int] = defaultdict(int)

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
                score_breakdown = _compute_score_breakdown(task, today)
                deadline_slack_days = (task.due_date - day.date).days if task.due_date else None

                scheduled_so_far = day_scheduled_minutes[day.date] + task.estimated_minutes
                available = day_available.get(day.date, 480)
                day_load_percent = round(scheduled_so_far / available * 100, 1) if available else 0

                warnings = []
                if deadline_slack_days is not None:
                    if deadline_slack_days < 0:
                        warnings.append({
                            "type": "past_deadline",
                            "message": f"Scheduled {abs(deadline_slack_days)} day(s) after deadline"
                        })
                    elif deadline_slack_days == 0:
                        warnings.append({
                            "type": "deadline_day",
                            "message": "Scheduled on deadline day"
                        })
                    elif deadline_slack_days <= 2:
                        warnings.append({
                            "type": "deadline_close",
                            "message": f"Only {deadline_slack_days} day(s) before deadline"
                        })

                if day_load_percent > 90:
                    warnings.append({
                        "type": "day_overload",
                        "message": f"Day is {day_load_percent}% loaded after this task"
                    })

                scheduled.append(ScheduledItem(
                    task_id=task.task_id,
                    scheduled_date=day.date,
                    start_time=start_time,
                    end_time=end_time,
                    risk_score=task.difficulty * task.dislike_score / 25.0,
                    rationale={
                        "score": _score(task, today),
                        "placed_on": str(day.date),
                        "reason": "greedy",
                        "score_breakdown": score_breakdown,
                        "risk_factors": {
                            "deadline_slack_days": deadline_slack_days,
                            "day_load_percent": day_load_percent,
                        },
                        "warnings": warnings,
                    },
                ))
                day_scheduled_minutes[day.date] += task.estimated_minutes
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
    today = date.today()
    cursors = {day: work_start for day in grid}
    day_scheduled_minutes: dict[date, int] = defaultdict(int)
    available_per_day = _minutes_between(work_start, work_end)
    sorted_tasks = sorted(tasks, key=lambda t: _score(t, today), reverse=True)

    for task in sorted_tasks:
        if not task.estimated_minutes:
            continue
        for day in grid:
            if _minutes_between(cursors[day], work_end) >= task.estimated_minutes:
                score_breakdown = _compute_score_breakdown(task, today)
                deadline_slack_days = (task.due_date - day).days if task.due_date else None

                scheduled_so_far = day_scheduled_minutes[day] + task.estimated_minutes
                day_load_percent = round(scheduled_so_far / available_per_day * 100, 1)

                warnings = []
                if deadline_slack_days is not None:
                    if deadline_slack_days < 0:
                        warnings.append({
                            "type": "past_deadline",
                            "message": f"Scheduled {abs(deadline_slack_days)} day(s) after deadline"
                        })
                    elif deadline_slack_days == 0:
                        warnings.append({
                            "type": "deadline_day",
                            "message": "Scheduled on deadline day"
                        })
                    elif deadline_slack_days <= 2:
                        warnings.append({
                            "type": "deadline_close",
                            "message": f"Only {deadline_slack_days} day(s) before deadline"
                        })

                if day_load_percent > 90:
                    warnings.append({
                        "type": "day_overload",
                        "message": f"Day is {day_load_percent}% loaded after this task"
                    })

                scheduled.append(ScheduledItem(
                    task_id=task.task_id,
                    scheduled_date=day,
                    start_time=cursors[day],
                    end_time=_add_minutes(cursors[day], task.estimated_minutes),
                    risk_score=task.difficulty * task.dislike_score / 25.0,
                    rationale={
                        "score": _score(task, today),
                        "placed_on": str(day),
                        "reason": "greedy",
                        "score_breakdown": score_breakdown,
                        "risk_factors": {
                            "deadline_slack_days": deadline_slack_days,
                            "day_load_percent": day_load_percent,
                        },
                        "warnings": warnings,
                    },
                ))
                day_scheduled_minutes[day] += task.estimated_minutes
                cursors[day] = _add_minutes(cursors[day], task.estimated_minutes)
                break

    return scheduled


def compute_risk_metrics(
    items: list[ScheduledItem],
    tasks: list[ScheduledTask],
    availability: list[DayAvailability] | None = None,
) -> dict:
    """Summarise risk across the full schedule.

    Returns a dict with both backward-compatible fields and new enhanced metrics:
        - scheduled: int - number of tasks scheduled
        - unscheduled: int - number of tasks that couldn't be scheduled
        - avg_risk: float - average risk score across scheduled items

        NEW:
        - deadline_slack_ratio: float - avg (due_date - scheduled) / duration
        - overload_ratio: float - max daily scheduled/available
        - context_switching_count: int - goal-to-goal transitions
        - burnout_likelihood: float - composite 0-1 score
        - critical_days: list[str] - days with overload > 90%
        - deadline_warnings: list[dict] - tasks near/past deadline
        - recommendations: list[str] - actionable suggestions
    """
    if not items:
        return {
            "scheduled": 0,
            "unscheduled": len(tasks),
            "avg_risk": 0.0,
            "deadline_slack_ratio": 0.0,
            "overload_ratio": 0.0,
            "context_switching_count": 0,
            "burnout_likelihood": 0.0,
            "critical_days": [],
            "deadline_warnings": [],
            "recommendations": ["No tasks scheduled. Add tasks with time estimates."] if tasks else [],
        }

    scheduled_ids = {str(i.task_id) for i in items}
    unscheduled_count = sum(1 for t in tasks if str(t.task_id) not in scheduled_ids)
    avg_risk = sum(i.risk_score for i in items) / len(items)

    day_metrics = _compute_day_metrics(items, availability)

    task_map = {t.task_id: t for t in tasks}
    slack_ratios = []
    for item in items:
        task = task_map.get(item.task_id)
        if task and task.due_date and task.estimated_minutes:
            slack_days = (task.due_date - item.scheduled_date).days
            duration_days = max(task.estimated_minutes / 480, 1)
            slack_ratios.append(slack_days / duration_days)

    deadline_slack_ratio = round(sum(slack_ratios) / len(slack_ratios), 2) if slack_ratios else 0.0

    max_load = max((m["load_percent"] for m in day_metrics.values()), default=0)
    overload_ratio = round(max_load / 100, 2)

    context_switching_count = _compute_context_switches(items, tasks)

    burnout_likelihood = _compute_burnout_likelihood(
        day_metrics, context_switching_count, unscheduled_count, len(tasks)
    )

    critical_days = [
        str(d) for d, m in sorted(day_metrics.items())
        if m["load_percent"] > 90
    ]

    deadline_warnings = _generate_deadline_warnings(items, tasks)

    recommendations = _generate_recommendations(
        day_metrics, deadline_warnings, context_switching_count,
        burnout_likelihood, unscheduled_count
    )

    quality_score = compute_schedule_quality_score(
        scheduled_count=len(items),
        total_tasks=len(tasks),
        avg_risk=avg_risk,
        deadline_slack_ratio=deadline_slack_ratio,
        overload_ratio=overload_ratio,
        context_switching_count=context_switching_count,
        burnout_likelihood=burnout_likelihood,
    )

    return {
        "scheduled": len(items),
        "unscheduled": unscheduled_count,
        "avg_risk": round(avg_risk, 3),
        "quality_score": quality_score,
        "deadline_slack_ratio": deadline_slack_ratio,
        "overload_ratio": overload_ratio,
        "context_switching_count": context_switching_count,
        "burnout_likelihood": burnout_likelihood,
        "critical_days": critical_days,
        "deadline_warnings": deadline_warnings,
        "recommendations": recommendations,
    }


def run(
    tasks: list[ScheduledTask],
    window_start: date,
    window_end: date,
    availability: list[DayAvailability] | None = None,
    validate: bool = True,
) -> tuple[list[ScheduledItem], dict]:
    """Entry point. Returns (scheduled_items, risk_summary).

    Args:
        tasks: Tasks to schedule
        window_start: Start of planning window
        window_end: End of planning window
        availability: Optional availability grid from calendar service.
                     If None, uses default work hours.
        validate: If True, validate inputs and raise ValidationError on failure.

    Raises:
        ValidationError: If validate=True and inputs fail validation.
    """
    if validate:
        errors = []
        errors.extend(validate_planning_window(window_start, window_end))
        if tasks:
            errors.extend(validate_tasks(tasks))
        if errors:
            raise ValidationError(errors)

    if not tasks:
        return [], {
            "scheduled": 0,
            "unscheduled": 0,
            "avg_risk": 0.0,
            "deadline_slack_ratio": 0.0,
            "overload_ratio": 0.0,
            "context_switching_count": 0,
            "burnout_likelihood": 0.0,
            "critical_days": [],
            "deadline_warnings": [],
            "recommendations": [],
        }

    if availability:
        items = _place_tasks_with_availability(tasks, availability)
    else:
        grid = build_availability_grid_default(window_start, window_end)
        items = _place_tasks_default(tasks, grid)

    risk_summary = compute_risk_metrics(items, tasks, availability)
    return items, risk_summary
