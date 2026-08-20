import { AxiosError, AxiosHeaders } from "axios";
import { describe, expect, it } from "vitest";

import { ApiRequestError, toApiError } from "./errors";

/** Build an AxiosError carrying the given response body, the way the axios
 * interceptor in client.ts hands one to a mutation's catch block. */
function axiosErrorWith(status: number, data: unknown): AxiosError {
  const error = new AxiosError("Request failed");
  error.response = {
    status,
    statusText: "",
    data,
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  };
  return error;
}

describe("toApiError", () => {
  it("reads a plain string detail (our own HTTPExceptions)", () => {
    const error = toApiError(
      axiosErrorWith(400, { detail: "Plan is not in proposed state" }),
      "fallback",
    );
    expect(error.messages).toEqual(["Plan is not in proposed state"]);
    expect(error.message).toBe("Plan is not in proposed state");
    expect(error.status).toBe(400);
  });

  it("reads a service rejection carrying a list of errors", () => {
    const error = toApiError(
      axiosErrorWith(422, {
        detail: {
          errors: [
            "planning_window_end must be after planning_window_start",
            "No pending tasks in scope",
          ],
        },
      }),
      "fallback",
    );
    expect(error.messages).toEqual([
      "planning_window_end must be after planning_window_start",
      "No pending tasks in scope",
    ]);
    expect(error.status).toBe(422);
  });

  it("reads pydantic validation entries and names the offending field", () => {
    const error = toApiError(
      axiosErrorWith(422, {
        detail: [
          {
            type: "date_from_datetime_parsing",
            loc: ["body", "planning_window_start"],
            msg: "Input should be a valid date or datetime",
          },
        ],
      }),
      "fallback",
    );
    expect(error.messages).toEqual([
      "planning_window_start: Input should be a valid date or datetime",
    ]);
  });

  it("keeps every message when the server sends several", () => {
    const error = toApiError(
      axiosErrorWith(422, {
        detail: [
          { loc: ["body", "planning_window_start"], msg: "Field required" },
          { loc: ["body", "planning_window_end"], msg: "Field required" },
        ],
      }),
      "fallback",
    );
    expect(error.messages).toHaveLength(2);
  });

  it("keeps .message readable so existing forms render something useful", () => {
    // goal-form.tsx reads `error.message`, not `error.messages`. A multi-error
    // response must not degrade to an empty or "[object Object]" string there.
    const error = toApiError(
      axiosErrorWith(422, { detail: { errors: ["First problem.", "Second problem."] } }),
      "fallback",
    );
    expect(error.message).toBe("First problem. Second problem.");
  });

  it("falls back when the response body carries no usable detail", () => {
    const error = toApiError(axiosErrorWith(500, "<html>oops</html>"), "Could not save");
    expect(error.messages).toEqual(["Could not save"]);
    expect(error.status).toBe(500);
  });

  it("falls back when detail is an empty error list", () => {
    const error = toApiError(
      axiosErrorWith(422, { detail: { errors: [] } }),
      "Could not generate plan",
    );
    expect(error.messages).toEqual(["Could not generate plan"]);
  });

  it("uses the fallback for a network failure, not axios's own message", () => {
    // No response means no status and no detail. Axios's "Network Error" is
    // not something to show a user, so the caller's fallback wins.
    const error = toApiError(new AxiosError("Network Error"), "Could not reach server");
    expect(error.status).toBeUndefined();
    expect(error.messages).toEqual(["Could not reach server"]);
  });

  it("keeps the message of a plain Error thrown outside axios", () => {
    const error = toApiError(new Error("Something local broke"), "fallback");
    expect(error.messages).toEqual(["Something local broke"]);
  });

  it("passes an ApiRequestError straight through", () => {
    const original = new ApiRequestError(["Already normalized"], 409);
    expect(toApiError(original, "fallback")).toBe(original);
  });

  it("uses the fallback for a thrown non-Error value", () => {
    expect(toApiError("just a string", "Could not save").messages).toEqual([
      "Could not save",
    ]);
  });
});
