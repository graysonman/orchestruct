import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "./page";

const replaceMock = vi.fn();
const refreshMock = vi.fn();
const searchParamsRef = { current: new URLSearchParams() };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, refresh: refreshMock }),
  useSearchParams: () => searchParamsRef.current,
}));

const loginMutateMock = vi.fn();
const loginPendingRef = { current: false };

vi.mock("@/lib/api/auth", () => ({
  useLogin: () => ({
    mutateAsync: loginMutateMock,
    isPending: loginPendingRef.current,
  }),
}));

function renderLogin() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <LoginPage />
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    refreshMock.mockClear();
    loginMutateMock.mockClear();
    loginPendingRef.current = false;
    searchParamsRef.current = new URLSearchParams();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders email and password fields", () => {
    renderLogin();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("shows validation errors when submitting empty form", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/invalid email format/i)).toBeInTheDocument();
    expect(await screen.findByText(/password is required/i)).toBeInTheDocument();
    expect(loginMutateMock).not.toHaveBeenCalled();
  });

  it("calls login mutation with valid input and navigates on success", async () => {
    loginMutateMock.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText(/email/i), "ada@example.com");
    await user.type(screen.getByLabelText(/password/i), "hunter2");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await vi.waitFor(() => {
      expect(loginMutateMock).toHaveBeenCalledWith({
        email: "ada@example.com",
        password: "hunter2",
      });
    });
    expect(replaceMock).toHaveBeenCalledWith("/dashboard");
  });

  it("surfaces backend error messages to the user", async () => {
    loginMutateMock.mockRejectedValueOnce(new Error("Invalid credentials"));
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText(/email/i), "ada@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrong-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("links to the Google OAuth route", () => {
    renderLogin();
    const link = screen.getByRole("link", { name: /continue with google/i });
    expect(link).toHaveAttribute("href", "/api/auth/google");
  });

  it("renders a message for a known OAuth error code", () => {
    searchParamsRef.current = new URLSearchParams("error=google_denied");
    renderLogin();
    expect(screen.getByRole("alert")).toHaveTextContent(/cancelled/i);
  });

  it("renders nothing for an unrecognized OAuth error code", () => {
    searchParamsRef.current = new URLSearchParams("error=<script>alert(1)</script>");
    renderLogin();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
