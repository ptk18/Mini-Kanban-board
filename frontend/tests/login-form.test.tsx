import { beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { LoginForm } from "@/components/LoginForm";
import { AuthProvider } from "@/lib/auth";
import { ApiError } from "@/lib/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

const api = vi.hoisted(() => ({
  login: vi.fn(),
  me: vi.fn(),
  getToken: vi.fn(() => null),
  setToken: vi.fn(),
  clearToken: vi.fn(),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, ...api };
});

const USER = { id: 1, email: "ada@example.com", display_name: "Ada", created_at: "2026-01-01T00:00:00Z" };

function renderForm() {
  return render(
    <AuthProvider>
      <LoginForm />
    </AuthProvider>,
  );
}

function fill(email: string, password: string) {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("LoginForm validation", () => {
  test("empty submit shows both errors and does not call the API", () => {
    renderForm();

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect(screen.getByText("Email is required")).toBeDefined();
    expect(screen.getByText("Password must be at least 8 characters")).toBeDefined();
    expect(screen.getByLabelText("Email").getAttribute("aria-invalid")).toBe("true");
    expect(api.login).not.toHaveBeenCalled();
  });

  test("malformed email and short password are rejected client-side", () => {
    renderForm();
    fill("not-an-email", "short");

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect(screen.getByText("Enter an email like name@example.com")).toBeDefined();
    expect(screen.getByText("Password must be at least 8 characters")).toBeDefined();
    expect(api.login).not.toHaveBeenCalled();
  });
});

describe("LoginForm submit", () => {
  test("valid submit logs in, stores the token and navigates to /boards", async () => {
    api.login.mockResolvedValue({ access_token: "jwt-123", token_type: "bearer", user: USER });
    renderForm();
    fill("Ada@Example.com", "correct horse");

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/boards"));
    expect(api.login).toHaveBeenCalledWith({ email: "Ada@Example.com", password: "correct horse" });
    expect(api.setToken).toHaveBeenCalledWith("jwt-123");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  test("a 401 from the API is shown and nothing navigates", async () => {
    api.login.mockRejectedValue(new ApiError(401, "Invalid email or password"));
    renderForm();
    fill("ada@example.com", "wrong password");

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByText("Invalid email or password")).toBeDefined();
    expect(push).not.toHaveBeenCalled();
    expect(api.setToken).not.toHaveBeenCalled();
  });

  test("a network failure shows a generic message", async () => {
    api.login.mockRejectedValue(new TypeError("Failed to fetch"));
    renderForm();
    fill("ada@example.com", "correct horse");

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByText("Could not reach the server")).toBeDefined();
  });
});
