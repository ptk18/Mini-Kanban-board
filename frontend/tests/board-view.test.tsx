import { beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { BoardView } from "@/components/board/BoardView";
import { AuthProvider } from "@/lib/auth";
import { board, cards, columns, members } from "./fixtures";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const api = vi.hoisted(() => ({
  getBoard: vi.fn(),
  listCards: vi.fn(),
  listMembers: vi.fn(),
  updateColumn: vi.fn(),
  deleteColumn: vi.fn(),
  createColumn: vi.fn(),
  createCard: vi.fn(),
  updateCard: vi.fn(),
  getToken: vi.fn(() => null),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, ...api };
});

function renderBoard() {
  return render(
    <AuthProvider>
      <BoardView boardId={1} />
    </AuthProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getBoard.mockResolvedValue(board);
  api.listCards.mockResolvedValue(cards);
  api.listMembers.mockResolvedValue(members);
});

describe("BoardView rendering", () => {
  test("renders the columns in order with their cards", async () => {
    renderBoard();

    expect(await screen.findByRole("heading", { level: 1, name: "Roadmap" })).toBeDefined();
    const sections = screen.getAllByRole("region");
    expect(sections.map((s) => s.getAttribute("aria-label"))).toEqual(["To Do", "In Progress", "Done"]);

    const todo = within(sections[0]);
    expect(todo.getAllByRole("listitem").map((li) => li.textContent)).toHaveLength(2);
    expect(todo.getByText("Write tests")).toBeDefined();
    expect(todo.getByText("Ship it")).toBeDefined();
    expect(within(sections[1]).queryAllByRole("listitem")).toHaveLength(0);
    expect(within(sections[2]).getByText("Set up CI")).toBeDefined();
  });

  test("a card shows priority, due date, labels and assignee; Done cards are never overdue", async () => {
    renderBoard();
    const sections = await screen.findAllByRole("region");

    const writeTests = within(sections[0]).getByText("Write tests").closest("li")!;
    expect(within(writeTests).getByText("high")).toBeDefined();
    expect(within(writeTests).getByText("overdue 2020-01-01")).toBeDefined();
    expect(within(writeTests).getByText("bug")).toBeDefined();
    expect(within(writeTests).getByText("Grace")).toBeDefined();

    const done = within(sections[2]).getByText("Set up CI").closest("li")!;
    expect(within(done).getByText("due 2020-01-01")).toBeDefined();
  });

  test("loads board, cards and members once and again when the tab regains focus", async () => {
    renderBoard();
    await screen.findByRole("heading", { level: 1, name: "Roadmap" });
    expect(api.listCards).toHaveBeenCalledTimes(1);

    fireEvent(window, new Event("focus"));

    await waitFor(() => expect(api.listCards).toHaveBeenCalledTimes(2));
  });
});

describe("BoardView column management", () => {
  test("column rename: click the header, type, Enter → PATCH and refetch", async () => {
    api.updateColumn.mockResolvedValue({ ...columns[0], name: "Backlog" });
    renderBoard();
    await screen.findByRole("heading", { level: 1, name: "Roadmap" });

    fireEvent.click(screen.getByRole("button", { name: /^To Do/ }));
    const input = screen.getByRole("textbox", { name: "Rename To Do" });
    fireEvent.change(input, { target: { value: " Backlog " } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(api.updateColumn).toHaveBeenCalledWith(10, { name: "Backlog" }));
    await waitFor(() => expect(api.getBoard).toHaveBeenCalledTimes(2));
  });

  test("Escape cancels a column rename without calling the API", async () => {
    renderBoard();
    await screen.findByRole("heading", { level: 1, name: "Roadmap" });

    fireEvent.click(screen.getByRole("button", { name: /^In Progress/ }));
    fireEvent.keyDown(screen.getByRole("textbox", { name: "Rename In Progress" }), { key: "Escape" });

    expect(screen.getByRole("button", { name: /^In Progress/ })).toBeDefined();
    expect(api.updateColumn).not.toHaveBeenCalled();
  });

  test("deleting a column explains what happens to its cards and only proceeds on confirm", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderBoard();
    await screen.findByRole("heading", { level: 1, name: "Roadmap" });

    fireEvent.click(screen.getByRole("button", { name: "Delete To Do" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/still holds 2 cards.*Move them first/));
    expect(api.deleteColumn).not.toHaveBeenCalled();

    confirm.mockReturnValue(true);
    api.deleteColumn.mockResolvedValue(undefined);
    fireEvent.click(screen.getByRole("button", { name: "Delete In Progress" }));
    expect(confirm).toHaveBeenLastCalledWith('Delete the empty column "In Progress"? Nothing else changes.');
    await waitFor(() => expect(api.deleteColumn).toHaveBeenCalledWith(11));
  });

  test("add column posts the name and refetches", async () => {
    api.createColumn.mockResolvedValue({ id: 13, board_id: 1, name: "Review", position: 3, created_at: "" });
    renderBoard();
    await screen.findByRole("heading", { level: 1, name: "Roadmap" });

    fireEvent.change(screen.getByLabelText("New column name"), { target: { value: "Review" } });
    fireEvent.click(screen.getByRole("button", { name: "Add column" }));

    await waitFor(() => expect(api.createColumn).toHaveBeenCalledWith(1, "Review"));
    await waitFor(() => expect(api.getBoard).toHaveBeenCalledTimes(2));
  });
});

describe("BoardView cards", () => {
  test("add card at the bottom of a column", async () => {
    api.createCard.mockResolvedValue(cards[0]);
    renderBoard();
    await screen.findByRole("heading", { level: 1, name: "Roadmap" });

    fireEvent.change(screen.getByLabelText("Add card to Done"), { target: { value: "  Celebrate " } });
    fireEvent.submit(screen.getByLabelText("Add card to Done").closest("form")!);

    await waitFor(() => expect(api.createCard).toHaveBeenCalledWith(1, { title: "Celebrate", column_id: 12 }));
  });

  test("the status dropdown moves a card to another column", async () => {
    api.updateCard.mockResolvedValue({ ...cards[1], column_id: 11 });
    renderBoard();
    await screen.findByRole("heading", { level: 1, name: "Roadmap" });

    fireEvent.change(screen.getByRole("combobox", { name: "Move Ship it" }), { target: { value: "11" } });

    await waitFor(() => expect(api.updateCard).toHaveBeenCalledWith(101, { column_id: 11 }));
    await waitFor(() => expect(api.listCards).toHaveBeenCalledTimes(2));
  });
});
