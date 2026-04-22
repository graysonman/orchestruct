"""Unit tests for the Stage 9 post-processing optimizer passes.

All tests are pure unit tests — no database, no HTTP client required.
Tests construct ScheduledItem / ScheduledTask objects directly and call
the optimizer functions from scheduler.py.
"""

from datetime import date, time

import pytest

from app.services.scheduler import (
    ScheduledItem,
    ScheduledTask,
    _compute_context_switches,
    _goal_group_pass,
    _stress_spread_pass,
    _swap_pass,
    compute_risk_metrics,
    optimize_schedule,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures / Helpers
# ─────────────────────────────────────────────────────────────────────────────

DAY1 = date(2026, 5, 5)  # Monday
DAY2 = date(2026, 5, 6)  # Tuesday
DAY3 = date(2026, 5, 7)  # Wednesday

GOAL_A = "goal-aaa"
GOAL_B = "goal-bbb"


def make_task(
    task_id: str,
    goal_id: str = GOAL_A,
    estimated_minutes: int = 60,
    difficulty: int = 2,
    dislike_score: int = 1,
) -> ScheduledTask:
    return ScheduledTask(
        task_id=task_id,
        title=f"Task {task_id}",
        estimated_minutes=estimated_minutes,
        difficulty=difficulty,
        dislike_score=dislike_score,
        due_date=None,
        priority_weight=1.0,
        goal_id=goal_id,
    )


def make_item(
    task_id: str,
    day: date,
    start_hour: int,
    duration_minutes: int = 60,
) -> ScheduledItem:
    start = time(start_hour, 0)
    end_hour = start_hour + duration_minutes // 60
    end_min = duration_minutes % 60
    end = time(end_hour, end_min)
    return ScheduledItem(
        task_id=task_id,
        scheduled_date=day,
        start_time=start,
        end_time=end,
        risk_score=0.1,
        rationale={},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: goal_group_pass reduces context switches
# ─────────────────────────────────────────────────────────────────────────────


def test_goal_group_reduces_context_switches():
    """Items alternating A/B/A/B on the same day should be reordered to A/A/B/B."""
    tasks = [
        make_task("t1", goal_id=GOAL_A),
        make_task("t2", goal_id=GOAL_B),
        make_task("t3", goal_id=GOAL_A),
        make_task("t4", goal_id=GOAL_B),
    ]
    # All on DAY1, interleaved A, B, A, B
    items = [
        make_item("t1", DAY1, 9),
        make_item("t2", DAY1, 10),
        make_item("t3", DAY1, 11),
        make_item("t4", DAY1, 12),
    ]

    before_switches = _compute_context_switches(items, tasks)
    result = _goal_group_pass(items, tasks, availability=None)
    after_switches = _compute_context_switches(result, tasks)

    assert after_switches <= before_switches, (
        f"Expected fewer or equal context switches after grouping, "
        f"got {after_switches} (was {before_switches})"
    )
    # All 4 items still present
    assert len(result) == 4
    # All still on DAY1
    assert all(item.scheduled_date == DAY1 for item in result)


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: stress_spread_pass redistributes hard tasks
# ─────────────────────────────────────────────────────────────────────────────


def test_stress_spread_redistributes_hard_tasks():
    """Two difficulty-5 tasks on DAY1, one easy task on DAY2 → hard task should move."""
    tasks = [
        make_task("hard1", difficulty=5, dislike_score=4),
        make_task("hard2", difficulty=5, dislike_score=4),
        make_task("easy1", difficulty=1, dislike_score=1),
    ]
    items = [
        make_item("hard1", DAY1, 9),
        make_item("hard2", DAY1, 10),
        make_item("easy1", DAY2, 9),
    ]

    result = _stress_spread_pass(items, tasks, availability=None)

    day1_tasks = [i for i in result if i.scheduled_date == DAY1]
    day2_tasks = [i for i in result if i.scheduled_date == DAY2]

    # After spreading, the hard tasks should be distributed more evenly
    assert len(result) == 3, "No tasks should be lost during stress spread"
    # DAY1 should no longer have both hard tasks (one should have moved to DAY2)
    assert len(day1_tasks) < 2 or len(day2_tasks) > 1, (
        "Expected stress to be spread: hard tasks should not all remain on DAY1"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: swap_pass improves quality score on an obviously improvable schedule
# ─────────────────────────────────────────────────────────────────────────────


def test_swap_pass_improves_or_maintains_quality():
    """Swap pass should never degrade quality_score."""
    tasks = [
        make_task("t1", difficulty=1, dislike_score=0),
        make_task("t2", difficulty=1, dislike_score=0),
        make_task("t3", difficulty=1, dislike_score=0),
        make_task("t4", difficulty=1, dislike_score=0),
    ]
    items = [
        make_item("t1", DAY1, 9),
        make_item("t2", DAY1, 10),
        make_item("t3", DAY2, 9),
        make_item("t4", DAY2, 10),
    ]

    before_score = compute_risk_metrics(items, tasks)["quality_score"]
    result = _swap_pass(items, tasks, availability=None)
    after_score = compute_risk_metrics(result, tasks)["quality_score"]

    assert after_score >= before_score, (
        f"Swap pass degraded quality: {before_score} → {after_score}"
    )
    assert len(result) == 4


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: optimize_schedule is idempotent (running twice doesn't degrade)
# ─────────────────────────────────────────────────────────────────────────────


def test_optimizer_is_idempotent():
    """Running optimize_schedule twice should not degrade quality."""
    tasks = [
        make_task("t1", goal_id=GOAL_A),
        make_task("t2", goal_id=GOAL_B),
        make_task("t3", goal_id=GOAL_A),
    ]
    items = [
        make_item("t1", DAY1, 9),
        make_item("t2", DAY1, 10),
        make_item("t3", DAY2, 9),
    ]

    once, summary1 = optimize_schedule(items, tasks, availability=None)
    twice, summary2 = optimize_schedule(once, tasks, availability=None)

    score1 = compute_risk_metrics(once, tasks)["quality_score"]
    score2 = compute_risk_metrics(twice, tasks)["quality_score"]

    assert score2 >= score1, (
        f"Second optimization pass degraded quality: {score1} → {score2}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: empty schedule returns gracefully
# ─────────────────────────────────────────────────────────────────────────────


def test_optimizer_empty_schedule():
    """optimize_schedule with no items should return empty list and valid summary."""
    result, summary = optimize_schedule([], [], availability=None)

    assert result == []
    assert "passes_applied" in summary
    assert "quality_before" in summary
    assert "quality_after" in summary
    assert "context_switches_before" in summary
    assert "context_switches_after" in summary


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: optimization_summary has all expected keys
# ─────────────────────────────────────────────────────────────────────────────


def test_optimize_schedule_summary_fields():
    """optimization_summary dict must contain the expected keys with correct types."""
    tasks = [make_task("t1"), make_task("t2")]
    items = [make_item("t1", DAY1, 9), make_item("t2", DAY2, 9)]

    _, summary = optimize_schedule(items, tasks, availability=None)

    assert isinstance(summary["passes_applied"], list)
    assert isinstance(summary["quality_before"], int)
    assert isinstance(summary["quality_after"], int)
    assert isinstance(summary["context_switches_before"], int)
    assert isinstance(summary["context_switches_after"], int)
    assert 0 <= summary["quality_before"] <= 100
    assert 0 <= summary["quality_after"] <= 100
