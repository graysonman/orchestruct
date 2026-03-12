"""Unit tests for the scheduler service.

Tests validation, risk metrics, rationale generation, and scheduling logic.
"""

import pytest
from datetime import date, time, timedelta

from app.services.scheduler import (
    ValidationError,
    ScheduledTask,
    ScheduledItem,
    validate_planning_window,
    validate_tasks,
    _compute_score_breakdown,
    _compute_day_metrics,
    _compute_context_switches,
    _compute_burnout_likelihood,
    _generate_deadline_warnings,
    _generate_recommendations,
    compute_risk_metrics,
    compute_schedule_quality_score,
    run,
)
from app.services.availability_service import DayAvailability, TimeSlot


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def today():
    return date.today()


@pytest.fixture
def sample_tasks(today):
    """Create sample tasks for testing."""
    return [
        ScheduledTask(
            task_id="task-1",
            title="Task 1",
            estimated_minutes=60,
            difficulty=3,
            dislike_score=2,
            due_date=today + timedelta(days=3),
            priority_weight=1.0,
            goal_id="goal-a",
        ),
        ScheduledTask(
            task_id="task-2",
            title="Task 2",
            estimated_minutes=120,
            difficulty=4,
            dislike_score=3,
            due_date=today + timedelta(days=5),
            priority_weight=1.5,
            goal_id="goal-a",
        ),
        ScheduledTask(
            task_id="task-3",
            title="Task 3",
            estimated_minutes=90,
            difficulty=2,
            dislike_score=1,
            due_date=today + timedelta(days=2),
            priority_weight=2.0,
            goal_id="goal-b",
        ),
    ]


@pytest.fixture
def sample_availability(today):
    """Create sample availability grid for testing."""
    days = []
    for i in range(5):
        d = today + timedelta(days=i)
        days.append(DayAvailability(
            date=d,
            work_hours=TimeSlot(start=time(9, 0), end=time(17, 0)),
            busy_slots=[],
            free_slots=[TimeSlot(start=time(9, 0), end=time(17, 0))],
        ))
    return days


# ─────────────────────────────────────────────────────────────────────────────
# Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestValidatePlanningWindow:
    def test_valid_window(self, today):
        """Valid 7-day window starting today should pass."""
        errors = validate_planning_window(
            today, today + timedelta(days=6), today=today
        )
        assert errors == []

    def test_window_starts_in_past(self, today):
        """Window starting in the past should fail."""
        errors = validate_planning_window(
            today - timedelta(days=1), today + timedelta(days=6), today=today
        )
        assert len(errors) == 1
        assert "past" in errors[0].lower()

    def test_window_end_before_start(self, today):
        """Window ending before starting should fail."""
        errors = validate_planning_window(
            today + timedelta(days=5), today, today=today
        )
        assert len(errors) >= 1
        assert any("end" in e.lower() for e in errors)

    def test_window_too_long(self, today):
        """Window exceeding 14 days should fail."""
        errors = validate_planning_window(
            today, today + timedelta(days=15), today=today
        )
        assert len(errors) == 1
        assert "14 days" in errors[0]

    def test_single_day_window(self, today):
        """Single day window should pass."""
        errors = validate_planning_window(today, today, today=today)
        assert errors == []

    def test_fourteen_day_window(self, today):
        """Maximum 14-day window should pass."""
        errors = validate_planning_window(
            today, today + timedelta(days=13), today=today
        )
        assert errors == []


class TestValidateTasks:
    def test_valid_tasks(self, sample_tasks):
        """Valid tasks should pass."""
        errors = validate_tasks(sample_tasks)
        assert errors == []

    def test_zero_estimated_minutes(self, today):
        """Task with 0 minutes should fail."""
        tasks = [ScheduledTask(
            task_id="bad",
            title="Bad Task",
            estimated_minutes=0,
            difficulty=3,
            dislike_score=2,
            due_date=today,
            priority_weight=1.0,
        )]
        errors = validate_tasks(tasks)
        assert len(errors) == 1
        assert "estimated_minutes" in errors[0]

    def test_invalid_difficulty(self, today):
        """Task with difficulty outside 1-5 should fail."""
        tasks = [ScheduledTask(
            task_id="bad",
            title="Bad Task",
            estimated_minutes=60,
            difficulty=6,  # Invalid
            dislike_score=2,
            due_date=today,
            priority_weight=1.0,
        )]
        errors = validate_tasks(tasks)
        assert len(errors) == 1
        assert "difficulty" in errors[0]

    def test_multiple_errors(self, today):
        """Multiple invalid tasks should return multiple errors."""
        tasks = [
            ScheduledTask(
                task_id="bad1",
                title="Bad 1",
                estimated_minutes=0,
                difficulty=3,
                dislike_score=2,
                due_date=today,
                priority_weight=1.0,
            ),
            ScheduledTask(
                task_id="bad2",
                title="Bad 2",
                estimated_minutes=60,
                difficulty=0,  # Invalid
                dislike_score=2,
                due_date=today,
                priority_weight=1.0,
            ),
        ]
        errors = validate_tasks(tasks)
        assert len(errors) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Score Breakdown Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreBreakdown:
    def test_score_breakdown_with_due_date(self, today):
        """Score breakdown should include urgency based on due date."""
        task = ScheduledTask(
            task_id="t1",
            title="Task",
            estimated_minutes=60,
            difficulty=4,
            dislike_score=3,
            due_date=today + timedelta(days=5),
            priority_weight=2.0,
        )
        breakdown = _compute_score_breakdown(task, today)
        assert breakdown["difficulty"] == 4.0
        assert breakdown["dislike"] == 3.0
        assert breakdown["urgency"] == round(2.0 / 5, 2)  # priority / days

    def test_score_breakdown_no_due_date(self, today):
        """Score breakdown with no due date uses default 30 days."""
        task = ScheduledTask(
            task_id="t1",
            title="Task",
            estimated_minutes=60,
            difficulty=2,
            dislike_score=1,
            due_date=None,
            priority_weight=1.0,
        )
        breakdown = _compute_score_breakdown(task, today)
        assert breakdown["urgency"] == round(1.0 / 30, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Day Metrics Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDayMetrics:
    def test_empty_items(self):
        """Empty items should return empty metrics."""
        metrics = _compute_day_metrics([], None)
        assert metrics == {}

    def test_single_day_load(self, today):
        """Single task should compute correct load percentage."""
        items = [
            ScheduledItem(
                task_id="t1",
                scheduled_date=today,
                start_time=time(9, 0),
                end_time=time(11, 0),  # 120 minutes
                risk_score=0.5,
                rationale={},
            )
        ]
        availability = [DayAvailability(
            date=today,
            work_hours=TimeSlot(time(9, 0), time(17, 0)),
            busy_slots=[],
            free_slots=[TimeSlot(time(9, 0), time(17, 0))],  # 480 minutes
        )]
        metrics = _compute_day_metrics(items, availability)
        assert today in metrics
        assert metrics[today]["scheduled_minutes"] == 120
        assert metrics[today]["available_minutes"] == 480
        assert metrics[today]["load_percent"] == 25.0


# ─────────────────────────────────────────────────────────────────────────────
# Context Switching Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestContextSwitches:
    def test_no_switches_same_goal(self, today):
        """Tasks from same goal should have no switches."""
        tasks = [
            ScheduledTask("t1", "T1", 60, 3, 2, today, 1.0, "goal-a"),
            ScheduledTask("t2", "T2", 60, 3, 2, today, 1.0, "goal-a"),
        ]
        items = [
            ScheduledItem("t1", today, time(9, 0), time(10, 0), 0.5, {}),
            ScheduledItem("t2", today, time(10, 0), time(11, 0), 0.5, {}),
        ]
        switches = _compute_context_switches(items, tasks)
        assert switches == 0

    def test_switches_different_goals(self, today):
        """Tasks from different goals should count switches."""
        tasks = [
            ScheduledTask("t1", "T1", 60, 3, 2, today, 1.0, "goal-a"),
            ScheduledTask("t2", "T2", 60, 3, 2, today, 1.0, "goal-b"),
            ScheduledTask("t3", "T3", 60, 3, 2, today, 1.0, "goal-a"),
        ]
        items = [
            ScheduledItem("t1", today, time(9, 0), time(10, 0), 0.5, {}),
            ScheduledItem("t2", today, time(10, 0), time(11, 0), 0.5, {}),
            ScheduledItem("t3", today, time(11, 0), time(12, 0), 0.5, {}),
        ]
        switches = _compute_context_switches(items, tasks)
        assert switches == 2  # a->b, b->a


# ─────────────────────────────────────────────────────────────────────────────
# Burnout Likelihood Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBurnoutLikelihood:
    def test_low_burnout_normal_load(self, today):
        """Normal load should have low burnout."""
        day_metrics = {
            today: {"load_percent": 50, "task_count": 2},
            today + timedelta(days=1): {"load_percent": 60, "task_count": 3},
        }
        burnout = _compute_burnout_likelihood(day_metrics, 1, 0, 5)
        assert burnout < 0.3

    def test_high_burnout_overloaded(self, today):
        """Overloaded days should increase burnout."""
        day_metrics = {
            today: {"load_percent": 95, "task_count": 5},
            today + timedelta(days=1): {"load_percent": 90, "task_count": 5},
        }
        burnout = _compute_burnout_likelihood(day_metrics, 8, 3, 10)
        assert burnout > 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Deadline Warnings Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDeadlineWarnings:
    def test_past_deadline_warning(self, today):
        """Task scheduled after deadline should generate high severity warning."""
        tasks = [ScheduledTask(
            "t1", "Task 1", 60, 3, 2, today, 1.0
        )]
        items = [ScheduledItem(
            "t1", today + timedelta(days=2), time(9, 0), time(10, 0), 0.5, {}
        )]
        warnings = _generate_deadline_warnings(items, tasks)
        assert len(warnings) == 1
        assert warnings[0]["type"] == "past_deadline"
        assert warnings[0]["severity"] == "high"

    def test_deadline_day_warning(self, today):
        """Task scheduled on deadline day should generate medium warning."""
        tasks = [ScheduledTask(
            "t1", "Task 1", 60, 3, 2, today + timedelta(days=2), 1.0
        )]
        items = [ScheduledItem(
            "t1", today + timedelta(days=2), time(9, 0), time(10, 0), 0.5, {}
        )]
        warnings = _generate_deadline_warnings(items, tasks)
        assert len(warnings) == 1
        assert warnings[0]["type"] == "deadline_day"
        assert warnings[0]["severity"] == "medium"

    def test_no_warning_plenty_of_slack(self, today):
        """Task with plenty of deadline slack should have no warning."""
        tasks = [ScheduledTask(
            "t1", "Task 1", 60, 3, 2, today + timedelta(days=10), 1.0
        )]
        items = [ScheduledItem(
            "t1", today, time(9, 0), time(10, 0), 0.5, {}
        )]
        warnings = _generate_deadline_warnings(items, tasks)
        assert len(warnings) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Recommendations Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestScheduleQualityScore:
    def test_perfect_schedule(self):
        """All tasks scheduled, low risk should score 85+."""
        score = compute_schedule_quality_score(
            scheduled_count=5,
            total_tasks=5,
            avg_risk=0.1,
            deadline_slack_ratio=2.0,
            overload_ratio=0.5,
            context_switching_count=2,
            burnout_likelihood=0.1,
        )
        assert score >= 85

    def test_poor_schedule(self):
        """Many issues should score below 50."""
        score = compute_schedule_quality_score(
            scheduled_count=2,
            total_tasks=5,  # 60% unscheduled
            avg_risk=0.8,
            deadline_slack_ratio=0.5,
            overload_ratio=1.0,  # Fully loaded
            context_switching_count=5,
            burnout_likelihood=0.9,
        )
        assert score < 50

    def test_empty_schedule(self):
        """No tasks should return 100."""
        score = compute_schedule_quality_score(
            scheduled_count=0,
            total_tasks=0,
            avg_risk=0.0,
            deadline_slack_ratio=0.0,
            overload_ratio=0.0,
            context_switching_count=0,
            burnout_likelihood=0.0,
        )
        assert score == 100

    def test_deadline_slack_bonus(self):
        """Good deadline slack should improve score."""
        base_score = compute_schedule_quality_score(
            scheduled_count=5, total_tasks=5, avg_risk=0.2,
            deadline_slack_ratio=1.0,  # No bonus
            overload_ratio=0.5, context_switching_count=2, burnout_likelihood=0.2,
        )
        bonus_score = compute_schedule_quality_score(
            scheduled_count=5, total_tasks=5, avg_risk=0.2,
            deadline_slack_ratio=2.0,  # Gets +5 bonus
            overload_ratio=0.5, context_switching_count=2, burnout_likelihood=0.2,
        )
        assert bonus_score == base_score + 5


class TestRecommendations:
    def test_overload_recommendation(self, today):
        """Should recommend redistribution for overloaded days."""
        day_metrics = {
            today: {"load_percent": 95, "task_count": 5},
        }
        recs = _generate_recommendations(day_metrics, [], 0, 0.2, 0)
        assert any("redistrib" in r.lower() for r in recs)

    def test_unscheduled_recommendation(self, today):
        """Should recommend extending window for unscheduled tasks."""
        recs = _generate_recommendations({}, [], 0, 0.2, 3)
        assert any("could not be scheduled" in r.lower() for r in recs)

    def test_burnout_recommendation(self, today):
        """Should warn about elevated burnout risk."""
        recs = _generate_recommendations({}, [], 0, 0.7, 0)
        assert any("burnout" in r.lower() for r in recs)


# ─────────────────────────────────────────────────────────────────────────────
# Full Risk Metrics Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestComputeRiskMetrics:
    def test_empty_items(self, sample_tasks):
        """Empty items should return base metrics."""
        metrics = compute_risk_metrics([], sample_tasks)
        assert metrics["scheduled"] == 0
        assert metrics["unscheduled"] == len(sample_tasks)
        assert metrics["avg_risk"] == 0.0
        assert "recommendations" in metrics

    def test_all_scheduled(self, today, sample_availability):
        """All tasks scheduled should show correct counts."""
        tasks = [ScheduledTask(
            "t1", "Task", 60, 3, 2, today + timedelta(days=3), 1.0
        )]
        items = [ScheduledItem(
            "t1", today, time(9, 0), time(10, 0), 0.24, {}
        )]
        metrics = compute_risk_metrics(items, tasks, sample_availability)
        assert metrics["scheduled"] == 1
        assert metrics["unscheduled"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests - run()
# ─────────────────────────────────────────────────────────────────────────────


class TestRun:
    def test_run_with_validation_error(self, today, sample_tasks):
        """Invalid window should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            run(
                sample_tasks,
                today - timedelta(days=1),  # Past date
                today + timedelta(days=6),
                validate=True,
            )
        assert len(exc_info.value.errors) > 0

    def test_run_without_validation(self, today, sample_tasks):
        """Validation can be disabled."""
        items, metrics = run(
            sample_tasks,
            today - timedelta(days=1),  # Would normally fail
            today + timedelta(days=6),
            validate=False,
        )
        # Should not raise, returns results

    def test_run_schedules_tasks(self, today, sample_tasks, sample_availability):
        """Tasks should be scheduled successfully."""
        items, metrics = run(
            sample_tasks,
            today,
            today + timedelta(days=4),
            availability=sample_availability,
            validate=True,
        )
        assert len(items) > 0
        assert metrics["scheduled"] > 0

    def test_run_returns_enhanced_metrics(self, today, sample_tasks, sample_availability):
        """Risk summary should include all new fields."""
        items, metrics = run(
            sample_tasks,
            today,
            today + timedelta(days=4),
            availability=sample_availability,
        )
        # Check all new fields exist
        assert "deadline_slack_ratio" in metrics
        assert "overload_ratio" in metrics
        assert "context_switching_count" in metrics
        assert "burnout_likelihood" in metrics
        assert "critical_days" in metrics
        assert "deadline_warnings" in metrics
        assert "recommendations" in metrics

    def test_run_returns_enriched_rationale(self, today, sample_tasks, sample_availability):
        """Scheduled items should have enriched rationale."""
        items, _ = run(
            sample_tasks,
            today,
            today + timedelta(days=4),
            availability=sample_availability,
        )
        assert len(items) > 0
        rationale = items[0].rationale
        # Check backward compatible fields
        assert "score" in rationale
        assert "placed_on" in rationale
        assert "reason" in rationale
        # Check new fields
        assert "score_breakdown" in rationale
        assert "risk_factors" in rationale
        assert "warnings" in rationale

    def test_run_empty_tasks(self, today):
        """Empty task list should return empty results with full structure."""
        items, metrics = run([], today, today + timedelta(days=6))
        assert items == []
        assert metrics["scheduled"] == 0
        assert "recommendations" in metrics
