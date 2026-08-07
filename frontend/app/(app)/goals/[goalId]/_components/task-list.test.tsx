import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Task } from "@/lib/api/tasks";

import { TaskList } from "./task-list";

const tasksRef = {
  current: { data: [] as Task[], isPending: false, error: null as Error | null },
};
const updateMock = vi.fn();
const deleteMock = vi.fn();

vi.mock("@/lib/api/tasks", () => ({
  useTasks: () => tasksRef.current,
  useUpdateTask: () => ({ mutate: updateMock, isPending: false }),
  useDeleteTask: () => ({ mutate: deleteMock, isPending: false }),
}));

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "t1",
    goal_id: "g1",
    title: "Write the spec",
    description: null,
    estimated_minutes: null,
    difficulty: null,
    due_date: null,
    dislike_score: 0,
    owner_user_id: null,
    prerequisites: null,
    status: "pending",
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
      <TaskList goalId="g1" />
    </QueryClientProvider>,
  );
}

describe("TaskList", () => {
  beforeEach(() => {
    tasksRef.current = { data: [], isPending: false, error: null };
    updateMock.mockClear();
    deleteMock.mockClear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading state", () => {
    tasksRef.current = { data: [], isPending: true, error: null };
    renderList();
    expect(screen.getByText(/loading tasks/i)).toBeInTheDocument();
  });

  it("shows an error state", () => {
    tasksRef.current = { data: [], isPending: false, error: new Error("boom") };
    renderList();
    expect(screen.getByRole("alert")).toHaveTextContent(/could not load tasks/i);
  });

  it("shows an empty state", () => {
    renderList();
    expect(screen.getByText(/no tasks yet/i)).toBeInTheDocument();
  });

  it("renders task details with a formatted estimate", () => {
    tasksRef.current = {
      data: [
        makeTask({
          estimated_minutes: 90,
          difficulty: 3,
          dislike_score: 2,
          due_date: "2026-01-01",
        }),
      ],
      isPending: false,
      error: null,
    };
    renderList();

    expect(screen.getByText("Write the spec")).toBeInTheDocument();
    expect(screen.getByText("1h 30m")).toBeInTheDocument();
    expect(screen.getByText("3/5")).toBeInTheDocument();
    // Date-only value must not shift a day west of UTC.
    expect(screen.getByText("01/01/2026")).toBeInTheDocument();
  });

  it("renders sub-hour estimates in minutes", () => {
    tasksRef.current = {
      data: [makeTask({ estimated_minutes: 45 })],
      isPending: false,
      error: null,
    };
    renderList();
    expect(screen.getByText("45m")).toBeInTheDocument();
  });

  it("renders whole-hour estimates without stray minutes", () => {
    tasksRef.current = {
      data: [makeTask({ estimated_minutes: 120 })],
      isPending: false,
      error: null,
    };
    renderList();
    expect(screen.getByText("2h")).toBeInTheDocument();
  });

  it("counts how many tasks are eligible for scheduling", () => {
    tasksRef.current = {
      data: [
        makeTask({ id: "t1", status: "pending" }),
        makeTask({ id: "t2", status: "completed" }),
        makeTask({ id: "t3", status: "pending" }),
      ],
      isPending: false,
      error: null,
    };
    renderList();
    expect(screen.getByText("2 of 3 eligible for scheduling")).toBeInTheDocument();
  });

  it("changes status from the dropdown", async () => {
    tasksRef.current = { data: [makeTask()], isPending: false, error: null };
    const user = userEvent.setup();
    renderList();

    await user.selectOptions(screen.getByLabelText(/status for write the spec/i), "completed");
    expect(updateMock).toHaveBeenCalledWith({ id: "t1", status: "completed" });
  });

  it("keeps an unrecognized status visible in the dropdown", () => {
    tasksRef.current = {
      data: [makeTask({ status: "deferred" })],
      isPending: false,
      error: null,
    };
    renderList();
    const select = screen.getByLabelText<HTMLSelectElement>(
      /status for write the spec/i,
    );
    expect(select.value).toBe("deferred");
  });

  it("advances a pending task with one click", async () => {
    tasksRef.current = { data: [makeTask()], isPending: false, error: null };
    const user = userEvent.setup();
    renderList();

    await user.click(screen.getByRole("button", { name: /move to in progress/i }));
    expect(updateMock).toHaveBeenCalledWith({ id: "t1", status: "in_progress" });
  });

  it("offers unblocking as the advance action for a blocked task", async () => {
    tasksRef.current = {
      data: [makeTask({ status: "blocked" })],
      isPending: false,
      error: null,
    };
    const user = userEvent.setup();
    renderList();

    await user.click(screen.getByRole("button", { name: /move to pending/i }));
    expect(updateMock).toHaveBeenCalledWith({ id: "t1", status: "pending" });
  });

  it("shows no advance button for a completed task", () => {
    tasksRef.current = {
      data: [makeTask({ status: "completed" })],
      isPending: false,
      error: null,
    };
    renderList();
    expect(screen.queryByRole("button", { name: /move to/i })).not.toBeInTheDocument();
  });

  it("deletes a task", async () => {
    tasksRef.current = { data: [makeTask()], isPending: false, error: null };
    const user = userEvent.setup();
    renderList();

    await user.click(screen.getByRole("button", { name: /delete/i }));
    expect(deleteMock).toHaveBeenCalledWith("t1");
  });
});
