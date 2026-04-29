// Hand-written domain types for fields the OpenAPI schema models as
// `dict | None` (loses fidelity in JSON Schema). Verified against:
//   - backend/app/services/scheduler.py:530-540 (rationale construction)
//   - backend/app/services/scheduler.py:623-718 (compute_risk_metrics)
//   - backend/tests/test_scheduler.py:542-559   (rationale assertions)

export type RationaleWarning = {
  type: "past_deadline" | "deadline_day" | "deadline_close" | "day_overload";
  message: string;
};

export type Rationale = {
  score: number;
  placed_on: string;
  reason: "greedy" | "team_greedy";
  score_breakdown: {
    urgency: number;
    difficulty: number;
    dislike: number;
  };
  risk_factors: {
    deadline_slack_days: number | null;
    day_load_percent: number;
  };
  warnings: RationaleWarning[];
  google_event_id?: string;
};

export type DeadlineWarning = {
  task_id: string;
  task_title: string;
  type: string;
  message: string;
  severity: "high" | "medium" | "low";
};

export type GoogleConflict = {
  google_event_id: string;
  title: string;
  conflict_type: "google_event_blocks_availability";
};

export type OptimizationDiff = {
  passes_applied: string[];
  quality_before: number;
  quality_after: number;
  context_switches_before: number;
  context_switches_after: number;
};

export type RiskSummary = {
  scheduled: number;
  unscheduled: number;
  avg_risk: number;
  quality_score: number;
  deadline_slack_ratio: number;
  overload_ratio: number;
  context_switching_count: number;
  burnout_likelihood: number;
  critical_days: string[];
  deadline_warnings: DeadlineWarning[];
  recommendations: string[];
  google_conflicts?: GoogleConflict[];
  optimization?: OptimizationDiff;
};
