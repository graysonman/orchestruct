import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/lib/api/errors";
import type { Plan, PlanItem } from "@/lib/api/plans";

import { PlanDetail } from "./plan-detail";

const planRef = { current: null as Plan | null };
const approveMock = vi.fn();
const rejectMock = vi.fn();
const startLogMock = vi.fn();

vi.mock("@/lib/api/plans", () => ({
  usePlan: () => ({ data: planRef.current }),
  useApprovePlan: () => ({ mutateAsync: approveMock, isPending: false }),
  useRejectPlan: () => ({ mutateAsync: rejectMock, isPending: false }),
}));

vi.mock("@/lib/api/worklogs", () => ({
  useCreateWorkLog: () => ({
    mutate: startLogMock,
    isPending: false,
    isError: false,
    isSuccess: false,
  }),
}));

function makeItem(overrides: Partial<PlanItem> = {}): PlanItem {
  return {
    id: "i1",
    plan_id: "p1",
    task_id: "t1",
    scheduled_date: "2026-08-18",
    start_time: "09:00:00",
    end_time: "10:30:00",
    risk_score: 0.2,
    rationale: null,
    created_at: "2026-08-17T00:00:00Z",
    assigned_to_user_id: null,
    task: { id: "t1", goal_id: "g1", title: "Draft the API layer", estimated_minutes: 90 },
    ...overrides,
  };
}

function makePlan(overrides: Partial<Plan> = {}): Plan {
  return {
    id: "p1",
    scope_type: "user",
    scope_id: "u1",
    planning_window_start: "2026-08-17",
    planning_window_end: "2026-08-23",
    status: "proposed",
    risk_summary: null,
    items: [makeItem()],
    created_at: "2026-08-17T00:00:00Z",
    updated_at: "2026-08-17T00:00:00Z",
    ...overrides,
  };
}

function renderDetail(plan: Plan) {
  planRef.current = plan;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PlanDetail planId={plan.id} initialPlan={plan} />
    </QueryClientProvider>,
  );
}

describe("PlanDetail", () => {
  beforeEach(() => {
    approveMock.mockReset().mockResolvedValue(makePlan({ status: "approved" }));
    rejectMock.mockReset().mockResolvedValue(makePlan({ status: "invalidated" }));
  });

  it("renders the window and status", () => {
    renderDetail(makePlan());
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Mon, Aug 17 – Sun, Aug 23",
    );
    expect(screen.getByText("Proposed")).toBeInTheDocument();
  });

  it("renders each scheduled block with its task title and time", () => {
    renderDetail(makePlan());
    expect(screen.getByText("Draft the API layer")).toBeInTheDocument();
    expect(screen.getByText("9:00 AM – 10:30 AM")).toBeInTheDocument();
  });

  it("groups blocks under their day heading", () => {
    renderDetail(
      makePlan({
        items: [
          makeItem({ id: "a", scheduled_date: "2026-08-18" }),
          makeItem({
            id: "b",
            scheduled_date: "2026-08-19",
            task: { id: "t2", goal_id: "g1", title: "Wire the panel", estimated_minutes: 45 },
          }),
        ],
      }),
    );
    expect(screen.getByText("Tue, Aug 18")).toBeInTheDocument();
    expect(screen.getByText("Wed, Aug 19")).toBeInTheDocument();
  });

  it("tells the user when the scheduler placed nothing", () => {
    renderDetail(makePlan({ items: [] }));
    expect(screen.getByText(/This plan is empty/)).toBeInTheDocument();
  });

  it("surfaces unscheduled work from the risk summary", () => {
    renderDetail(
      makePlan({ risk_summary: { scheduled: 3, unscheduled: 2, quality_score: 71 } }),
    );
    expect(screen.getByText(/2 tasks did not fit/)).toBeInTheDocument();
    expect(screen.getByText("71/100")).toBeInTheDocument();
  });

  it("ignores a risk summary whose values are the wrong type", () => {
    // risk_summary is an untyped dict on the backend, so this is reachable and
    // must not render "NaN/100".
    renderDetail(makePlan({ risk_summary: { quality_score: "high" } }));
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });

  it("offers approve and reject on a proposed plan", () => {
    renderDetail(makePlan({ status: "proposed" }));
    expect(screen.getByRole("button", { name: "Approve plan" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("offers only reject on an approved plan", () => {
    renderDetail(makePlan({ status: "approved" }));
    expect(screen.queryByRole("button", { name: "Approve plan" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("offers no actions on an invalidated plan", () => {
    renderDetail(makePlan({ status: "invalidated" }));
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
  });

  it("approves a plan", async () => {
    const user = userEvent.setup();
    renderDetail(makePlan({ status: "proposed" }));
    await user.click(screen.getByRole("button", { name: "Approve plan" }));
    expect(approveMock).toHaveBeenCalledTimes(1);
  });

  it("starts an open log at the real current time, not the scheduled time", async () => {
    // The block says 9:00, but starting one now means now — the scheduled
    // times describe the plan, not what is happening.
    const user = userEvent.setup();
    renderDetail(makePlan());

    await user.click(screen.getByRole("button", { name: "Start now" }));

    expect(startLogMock).toHaveBeenCalledTimes(1);
    const payload = startLogMock.mock.calls[0][0];
    expect(payload.task_id).toBe("t1");
    expect(payload.ended_at).toBeNull();
    expect(payload.completed).toBe(false);
    expect(Date.now() - new Date(payload.started_at).getTime()).toBeLessThan(5000);
  });

  it("renders every message when the server rejects the action with several", async () => {
    // The payoff of ApiRequestError carrying a list: a multi-problem response
    // renders as multiple lines rather than only its first.
    approveMock.mockRejectedValue(
      new ApiRequestError(["Plan is not in proposed state", "Try regenerating."], 400),
    );
    const user = userEvent.setup();
    renderDetail(makePlan({ status: "proposed" }));

    await user.click(screen.getByRole("button", { name: "Approve plan" }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Plan is not in proposed state")).toBeInTheDocument();
    expect(within(alert).getByText("Try regenerating.")).toBeInTheDocument();
  });

  it("falls back to a generic message for a non-API failure", async () => {
    approveMock.mockRejectedValue(new TypeError("boom"));
    const user = userEvent.setup();
    renderDetail(makePlan({ status: "proposed" }));

    await user.click(screen.getByRole("button", { name: "Approve plan" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not approve plan",
    );
  });
});
