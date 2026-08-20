import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/lib/api/errors";
import type { PlanItem } from "@/lib/api/plans";

import { LogTimeForm } from "./log-time-form";

const createMock = vi.fn();

vi.mock("@/lib/api/worklogs", () => ({
  useCreateWorkLog: () => ({ mutateAsync: createMock, isPending: false }),
}));

function makeItem(overrides: Partial<PlanItem> = {}): PlanItem {
  return {
    id: "i1",
    plan_id: "p1",
    task_id: "t1",
    scheduled_date: "2026-08-18",
    start_time: "09:00:00",
    end_time: "10:30:00",
    risk_score: null,
    rationale: null,
    created_at: "2026-08-17T00:00:00Z",
    assigned_to_user_id: null,
    task: { id: "t1", goal_id: "g1", title: "Draft the API layer", estimated_minutes: 90 },
    ...overrides,
  };
}

function renderForm(onClose = vi.fn(), item = makeItem()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <LogTimeForm item={item} onClose={onClose} />
    </QueryClientProvider>,
  );
  return { onClose };
}

describe("LogTimeForm", () => {
  beforeEach(() => {
    createMock.mockReset().mockResolvedValue({});
  });

  it("prefills the scheduled times", () => {
    renderForm();
    expect(screen.getByLabelText("Started")).toHaveValue("09:00");
    expect(screen.getByLabelText("Ended")).toHaveValue("10:30");
    expect(screen.getByLabelText("Finished it")).toBeChecked();
  });

  it("submits the block's task and date", async () => {
    const user = userEvent.setup();
    const { onClose } = renderForm();

    await user.click(screen.getByRole("button", { name: "Save log" }));

    expect(createMock).toHaveBeenCalledTimes(1);
    const payload = createMock.mock.calls[0][0];
    expect(payload.task_id).toBe("t1");
    expect(payload.completed).toBe(true);
    // Anchored to the scheduled day, not today.
    expect(new Date(payload.started_at).getDate()).toBe(18);
    expect(onClose).toHaveBeenCalled();
  });

  it("sends the corrected times when the user edits them", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.clear(screen.getByLabelText("Ended"));
    await user.type(screen.getByLabelText("Ended"), "11:45");
    await user.click(screen.getByRole("button", { name: "Save log" }));

    const payload = createMock.mock.calls[0][0];
    const ended = new Date(payload.ended_at);
    expect(ended.getHours()).toBe(11);
    expect(ended.getMinutes()).toBe(45);
  });

  it("refuses to submit an end time before the start", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.clear(screen.getByLabelText("Ended"));
    await user.type(screen.getByLabelText("Ended"), "08:00");
    await user.click(screen.getByRole("button", { name: "Save log" }));

    expect(createMock).not.toHaveBeenCalled();
    expect(
      await screen.findByText("End time must be after the start time"),
    ).toBeInTheDocument();
  });

  it("refuses to mark a log finished with no end time", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.clear(screen.getByLabelText("Ended"));
    await user.click(screen.getByRole("button", { name: "Save log" }));

    expect(createMock).not.toHaveBeenCalled();
    expect(
      await screen.findByText("An end time is required to mark this finished"),
    ).toBeInTheDocument();
  });

  it("saves an open log when the user unchecks finished", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.clear(screen.getByLabelText("Ended"));
    await user.click(screen.getByLabelText("Finished it"));
    await user.click(screen.getByRole("button", { name: "Save log" }));

    const payload = createMock.mock.calls[0][0];
    expect(payload.ended_at).toBeNull();
    expect(payload.completed).toBe(false);
  });

  it("surfaces server errors and stays open", async () => {
    createMock.mockRejectedValue(
      new ApiRequestError(["ended_at must be after started_at"], 422),
    );
    const user = userEvent.setup();
    const { onClose } = renderForm();

    await user.click(screen.getByRole("button", { name: "Save log" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "ended_at must be after started_at",
    );
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes without saving on cancel", async () => {
    const user = userEvent.setup();
    const { onClose } = renderForm();

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(createMock).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });
});
