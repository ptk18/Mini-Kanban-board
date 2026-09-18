import { beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { InviteJoin } from "@/components/InviteJoin";
import { AuthProvider } from "@/lib/auth";
import { ApiError } from "@/lib/api";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
}));

const api = vi.hoisted(() => ({
  getToken: vi.fn<() => string | null>(() => null),
  me: vi.fn(),
  clearToken: vi.fn(),
  joinByInvite: vi.fn(),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, ...api };
});

const USER = { id: 2, email: "grace@example.com", display_name: "Grace", created_at: "" };

function renderInvite(token = "abc123") {
  return render(
    <AuthProvider>
      <InviteJoin token={token} />
    </AuthProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("/invite/[token]", () => {
  test("a logged-in user joins and is redirected to the board", async () => {
    api.getToken.mockReturnValue("jwt");
    api.me.mockResolvedValue(USER);
    api.joinByInvite.mockResolvedValue({ board: { id: 7, name: "Roadmap" }, joined: true });

    renderInvite();

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/boards/7"));
    expect(api.joinByInvite).toHaveBeenCalledWith("abc123");
  });

  test("a signed-out user is sent to login with this page as the return address", async () => {
    api.getToken.mockReturnValue(null);

    renderInvite();

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Finvite%2Fabc123"));
    expect(api.joinByInvite).not.toHaveBeenCalled();
  });

  test("an invalid link shows the server's message and does not redirect", async () => {
    api.getToken.mockReturnValue("jwt");
    api.me.mockResolvedValue(USER);
    api.joinByInvite.mockRejectedValue(new ApiError(404, "Invalid invite link"));

    renderInvite("nope");

    expect(await screen.findByText("Invalid invite link")).toBeDefined();
    expect(replace).not.toHaveBeenCalled();
  });
});
