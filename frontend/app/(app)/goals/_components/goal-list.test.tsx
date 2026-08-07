import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Goal } from "@/lib/api/goals";

import { GoalList } from "./goal-list";

const goalsRef = {
  current: { data: [] as Goal[], isPending: false, error: null as Error | null },
};
const updateMock = vi.fn();
const deleteMock = vi.fn();

vi.mock("@/lib/api/goals", () => ({
  useGoals: () => goalsRef.current,
  useUpdateGoal: () => ({ mutate: updateMock, isPending: false }),
  useDeleteGoal: () => ({ mutate: deleteMock, isPending: false }),
}));

function makeGoal(overrides: Partial<Goal> = {}): Goal {
  return {
    id: "g1",
    title: "Ship v1",
    description: "Get it out the door",
    scope_type: "user",
    scope_id: "u1",
    success_metric_type: null,
    target_value: null,
    target_date: null,
    priority_weight: 1,
    min_weekly_hours: null,
    max_weekly_hours: null,
    constraints: null,
    is_active: true,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

function renderList() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <GoalList />
    </QueryClientProvider>,
  );
}

describe("GoalList", () => {
  beforeEach(() => {
    goalsRef.current = { data: [], isPending: false, error: null };
    updateMock.mockClear();
    deleteMock.mockClear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading state", () => {
    goalsRef.current = { data: [], isPending: true, error: null };
    renderList();
    expect(screen.getByText(/loading goals/i)).toBeInTheDocument();
  });

  it("shows an error state", () => {
    goalsRef.current = { data: [], isPending: false, error: new Error("boom") };
    renderList();
    expect(screen.getByRole("alert")).toHaveTextContent(/could not load goals/i);
  });

  it("shows an empty state", () => {
    renderList();
    expect(screen.getByText(/no goals yet/i)).toBeInTheDocument();
  });

  it("renders a goal with its details", () => {
    goalsRef.current = {
      data: [
        makeGoal({
          success_metric_type: "features",
          target_value: 12,
          min_weekly_hours: 4,
          max_weekly_hours: 10,
        }),
      ],
      isPending: false,
      error: null,
    };
    renderList();

    expect(screen.getByText("Ship v1")).toBeInTheDocument();
    expect(screen.getByText(/features → 12/)).toBeInTheDocument();
    expect(screen.getByText(/4–10 h\/week/)).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders a date-only target_date without timezone drift", () => {
    goalsRef.current = {
      data: [makeGoal({ target_date: "2026-01-01" })],
      isPending: false,
      error: null,
    };
    renderList();
    // Naive `new Date("2026-01-01")` would render 12/31/2025 west of UTC.
    expect(screen.getByText("01/01/2026")).toBeInTheDocument();
  });

  it("archives an active goal", async () => {
    goalsRef.current = { data: [makeGoal()], isPending: false, error: null };
    const user = userEvent.setup();
    renderList();

    await user.click(screen.getByRole("button", { name: /archive/i }));
    expect(updateMock).toHaveBeenCalledWith({ id: "g1", is_active: false });
  });

  it("reactivates an archived goal", async () => {
    goalsRef.current = {
      data: [makeGoal({ is_active: false })],
      isPending: false,
      error: null,
    };
    const user = userEvent.setup();
    renderList();

    await user.click(screen.getByRole("button", { name: /reactivate/i }));
    expect(updateMock).toHaveBeenCalledWith({ id: "g1", is_active: true });
  });

  it("deletes a goal", async () => {
    goalsRef.current = { data: [makeGoal()], isPending: false, error: null };
    const user = userEvent.setup();
    renderList();

    await user.click(screen.getByRole("button", { name: /delete/i }));
    expect(deleteMock).toHaveBeenCalledWith("g1");
  });
});
