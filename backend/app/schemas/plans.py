import uuid
from datetime import date, time, datetime

from pydantic import BaseModel, Field

from app.models.base import ScopeType


# ─────────────────────────────────────────────────────────────────────────────
# Request Models
# ─────────────────────────────────────────────────────────────────────────────


class PlanGenerate(BaseModel):
    planning_window_start: date
    planning_window_end: date
    scope_type: ScopeType = ScopeType.USER
    scope_id: uuid.UUID | None = None  # team UUID when scope_type=TEAM


# ─────────────────────────────────────────────────────────────────────────────
# Typed Risk & Rationale Models (for documentation/validation)
# ─────────────────────────────────────────────────────────────────────────────


class ScoreBreakdown(BaseModel):
    """Breakdown of scheduling score components."""
    urgency: float = Field(description="Score from priority and deadline proximity")
    difficulty: float = Field(description="Task difficulty (1-5)")
    dislike: float = Field(description="User dislike score (0-5)")


class RiskFactors(BaseModel):
    """Risk factors for a scheduled item."""
    deadline_slack_days: int | None = Field(
        description="Days between scheduled date and deadline (negative = past deadline)"
    )
    day_load_percent: float = Field(description="Percentage of day's availability used")


class ItemWarning(BaseModel):
    """Warning for a scheduled item."""
    type: str = Field(description="Warning type: past_deadline, deadline_day, deadline_close, day_overload")
    message: str = Field(description="Human-readable warning message")


class EnrichedRationale(BaseModel):
    """Full rationale for task placement."""
    score: float = Field(description="Composite scheduling score")
    placed_on: str = Field(description="Date the task was placed on (ISO format)")
    reason: str = Field(description="Placement algorithm used (e.g., 'greedy')")
    score_breakdown: ScoreBreakdown
    risk_factors: RiskFactors
    warnings: list[ItemWarning] = Field(default_factory=list)


class DeadlineWarning(BaseModel):
    """Warning about deadline issues."""
    task_id: str
    task_title: str
    type: str = Field(description="past_deadline, deadline_day, deadline_close, unscheduled_urgent")
    message: str
    severity: str = Field(description="high, medium, or low")


class RiskSummary(BaseModel):
    """Enhanced risk summary for a plan."""
    # Backward compatible fields
    scheduled: int = Field(description="Number of tasks scheduled")
    unscheduled: int = Field(description="Number of tasks that couldn't be scheduled")
    avg_risk: float = Field(description="Average risk score (0-1)")

    # New enhanced metrics
    quality_score: int = Field(
        default=75,
        description="Overall schedule quality (0-100). 90+: excellent, 70-89: good, 50-69: acceptable, <50: poor"
    )
    deadline_slack_ratio: float = Field(
        default=0.0,
        description="Average (due_date - scheduled) / duration ratio"
    )
    overload_ratio: float = Field(
        default=0.0,
        description="Maximum daily scheduled/available ratio"
    )
    context_switching_count: int = Field(
        default=0,
        description="Number of goal-to-goal transitions in schedule"
    )
    burnout_likelihood: float = Field(
        default=0.0,
        description="Composite burnout risk score (0-1)"
    )
    critical_days: list[str] = Field(
        default_factory=list,
        description="Dates with >90% load"
    )
    deadline_warnings: list[DeadlineWarning] = Field(
        default_factory=list,
        description="Tasks near or past deadline"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable suggestions"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Response Models
# ─────────────────────────────────────────────────────────────────────────────

class PlanItemResponse(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    task_id: uuid.UUID
    scheduled_date: date
    start_time: time
    end_time: time
    risk_score: float | None
    rationale: dict | None
    created_at: datetime
    assigned_to_user_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}

class PlanResponse(BaseModel):
    id: uuid.UUID
    scope_type: ScopeType
    scope_id: uuid.UUID
    planning_window_start: date
    planning_window_end: date
    status: str
    risk_summary: dict | None
    items: list[PlanItemResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}