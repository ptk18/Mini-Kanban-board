import { beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { BoardList } from "@/components/BoardList";
import type { Board, BoardDetail } from "@/lib/api";

const api = vi.hoisted(() => ({
  listBoards: vi.fn(),
  createBoard: vi.fn(),
  renameBoard: vi.fn(),
  deleteBoard: vi.fn(),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, ...api };
});

const board = (overrides: Partial<Board>): Board => ({
  id: 1,
  name: "Roadmap",
  owner_id: 1,
  role: "owner",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});
const BOARDS = [board({ id: 1, name: "Roadmap", role: "owner" }), board({ id: 2, name: "Shared", role: "member", owner_id: 2 })];

beforeEach(() => {
  vi.clearAllMocks();
  api.listBoards.mockResolvedValue(BOARDS);
});

describe("BoardList rendering", () => {
  test("lists the boards from the API with links and roles", async () => {
    render(<BoardList />);

    expect(await screen.findByRole("link", { name: "Roadmap" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Roadmap" }).getAttribute("href")).toBe("/boards/1");
    expect(screen.getByRole("link", { name: "Shared" }).getAttribute("href")).toBe("/boards/2");
    expect(screen.getByText("owner")).toBeDefined();
    expect(screen.getByText("member")).toBeDefined();
  });

  test("delete is only offered on boards the user owns", async () => {
    render(<BoardList />);
    await screen.findByRole("link", { name: "Roadmap" });

    expect(screen.getByRole("button", { name: "Delete Roadmap" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Delete Shared" })).toBeNull();
    expect(screen.getByRole("button", { name: "Rename Shared" })).toBeDefined();
  });

  test("shows the empty state", async () => {
    api.listBoards.mockResolvedValue([]);
    render(<BoardList />);

    expect(await screen.findByText("No boards yet. Create one above.")).toBeDefined();
  });
});

describe("BoardList create", () => {
  test("submitting a name calls the API and appends the board", async () => {
    const created: BoardDetail = { ...board({ id: 3, name: "New one" }), columns: [] };
    api.createBoard.mockResolvedValue(created);
    render(<BoardList />);
    await screen.findByRole("link", { name: "Roadmap" });

    fireEvent.change(screen.getByLabelText("New board name"), { target: { value: "  New one  " } });
    fireEvent.click(screen.getByRole("button", { name: "Create board" }));

    expect(await screen.findByRole("link", { name: "New one" })).toBeDefined();
    expect(api.createBoard).toHaveBeenCalledWith("New one");
    expect((screen.getByLabelText("New board name") as HTMLInputElement).value).toBe("");
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });

  test("a blank name is rejected without calling the API", async () => {
    render(<BoardList />);
    await screen.findByRole("link", { name: "Roadmap" });

    fireEvent.click(screen.getByRole("button", { name: "Create board" }));

    expect(screen.getByText("Board name is required")).toBeDefined();
    expect(api.createBoard).not.toHaveBeenCalled();
  });
});

describe("BoardList rename and delete", () => {
  test("inline rename saves on Enter", async () => {
    api.renameBoard.mockResolvedValue(board({ id: 1, name: "Renamed" }));
    render(<BoardList />);
    await screen.findByRole("link", { name: "Roadmap" });

    fireEvent.click(screen.getByRole("button", { name: "Rename Roadmap" }));
    const input = screen.getByRole("textbox", { name: "Rename Roadmap" });
    fireEvent.change(input, { target: { value: "Renamed" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(await screen.findByRole("link", { name: "Renamed" })).toBeDefined();
    expect(api.renameBoard).toHaveBeenCalledWith(1, "Renamed");
  });

  test("Escape cancels a rename", async () => {
    render(<BoardList />);
    await screen.findByRole("link", { name: "Roadmap" });

    fireEvent.click(screen.getByRole("button", { name: "Rename Roadmap" }));
    const input = screen.getByRole("textbox", { name: "Rename Roadmap" });
    fireEvent.change(input, { target: { value: "Nope" } });
    fireEvent.keyDown(input, { key: "Escape" });

    expect(screen.getByRole("link", { name: "Roadmap" })).toBeDefined();
    expect(api.renameBoard).not.toHaveBeenCalled();
  });

  test("delete asks for confirmation and removes the board when confirmed", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    api.deleteBoard.mockResolvedValue(undefined);
    render(<BoardList />);
    await screen.findByRole("link", { name: "Roadmap" });

    fireEvent.click(screen.getByRole("button", { name: "Delete Roadmap" }));

    await waitFor(() => expect(screen.queryByRole("link", { name: "Roadmap" })).toBeNull());
    expect(api.deleteBoard).toHaveBeenCalledWith(1);
    expect(within(screen.getByRole("list")).getAllByRole("listitem")).toHaveLength(1);
  });

  test("delete does nothing when the confirmation is declined", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<BoardList />);
    await screen.findByRole("link", { name: "Roadmap" });

    fireEvent.click(screen.getByRole("button", { name: "Delete Roadmap" }));

    expect(api.deleteBoard).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Roadmap" })).toBeDefined();
  });
});
