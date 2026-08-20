import { AxiosError } from "axios";

/** Normalizes the several shapes FastAPI puts in `detail` into one Error.
 *
 * The backend answers a failed request with `detail`, but the value under that
 * key depends on who rejected the request:
 *
 *   1. Our own HTTPExceptions        detail: "Plan is not in proposed state"
 *   2. A service-level rejection     detail: { errors: ["...", "..."] }
 *   3. Pydantic body validation      detail: [{ loc, msg, type }, ...]
 *
 * Shape 1 is a single sentence, shapes 2 and 3 are lists — and the same
 * endpoint can return more than one of them. `POST /plans/generate` produces
 * shape 2 when the scheduler rejects the window (routers/plans.py) and shape 3
 * when the request body doesn't parse, both as a 422.
 *
 * Collapsing all three into a single string would throw away the list, so
 * ApiRequestError always exposes `messages`, and callers that only want one
 * line keep reading `.message` as before.
 */

/** Pydantic's per-field validation entry (shape 3). */
type ValidationDetail = {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
};

type DetailBody = {
  detail?: string | { errors?: unknown } | ValidationDetail[];
};

export class ApiRequestError extends Error {
  /** Every message the server sent, always at least one entry.
   *
   * A single-sentence error yields a one-element array so callers can render
   * `messages` unconditionally without special-casing length. */
  readonly messages: string[];

  /** HTTP status, when the failure came back from the server at all. Undefined
   * for network errors, where no response exists. */
  readonly status?: number;

  constructor(messages: string[], status?: number) {
    // `message` is what every existing caller reads — goal-form.tsx does
    // `error instanceof Error ? error.message : fallback`. Joining keeps those
    // call sites working without a change, and keeps multi-error responses
    // from silently rendering only their first line.
    super(messages.join(" "));
    this.name = "ApiRequestError";
    this.messages = messages;
    this.status = status;
  }
}

/** Render one pydantic validation entry as a sentence.
 *
 * `loc` is a path to the offending field, prefixed with "body" for request
 * bodies. Dropping that prefix leaves the field name the user actually saw on
 * the form.
 */
function formatValidationDetail(item: ValidationDetail): string {
  const msg = item.msg ?? "Invalid value";
  const path = (item.loc ?? []).filter(
    (segment) => segment !== "body" && segment !== "query",
  );
  return path.length > 0 ? `${path.join(".")}: ${msg}` : msg;
}

function isValidationDetailArray(value: unknown): value is ValidationDetail[] {
  return (
    Array.isArray(value) &&
    value.every((item) => typeof item === "object" && item !== null)
  );
}

/** Pull every message out of a response body, or null if it holds none. */
function messagesFromDetail(detail: unknown): string[] | null {
  // Shape 1 — a single sentence.
  if (typeof detail === "string" && detail.trim() !== "") {
    return [detail];
  }

  // Shape 3 — pydantic's list. Checked before shape 2 because both are
  // objects, but only this one is an array.
  if (isValidationDetailArray(detail)) {
    const messages = detail.map(formatValidationDetail);
    return messages.length > 0 ? messages : null;
  }

  // Shape 2 — a service rejection carrying its own list of plain strings.
  if (typeof detail === "object" && detail !== null && "errors" in detail) {
    const { errors } = detail as { errors?: unknown };
    if (Array.isArray(errors)) {
      const messages = errors
        .filter((entry): entry is string => typeof entry === "string")
        .filter((entry) => entry.trim() !== "");
      return messages.length > 0 ? messages : null;
    }
  }

  return null;
}

/** Convert anything thrown by an apiClient call into an ApiRequestError.
 *
 * `fallback` is used when the failure carried no usable detail — a network
 * error, an HTML error page from a proxy, or a body we don't recognize.
 */
export function toApiError(error: unknown, fallback: string): ApiRequestError {
  if (error instanceof ApiRequestError) return error;

  if (error instanceof AxiosError) {
    const status = error.response?.status;
    const body = error.response?.data as DetailBody | undefined;
    const messages = messagesFromDetail(body?.detail);
    if (messages) return new ApiRequestError(messages, status);

    // A response with no readable detail still knows its status, which is
    // more useful to a caller than the axios message ("Request failed with
    // status code 500").
    return new ApiRequestError([fallback], status);
  }

  if (error instanceof Error && error.message.trim() !== "") {
    return new ApiRequestError([error.message]);
  }

  return new ApiRequestError([fallback]);
}
