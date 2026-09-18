import { beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { CardModal, diffCard } from "@/components/card/CardModal";
import { AuthProvider } from "@/lib/auth";
import { card, cards, columns, members } from "./fixtures";

const api = vi.hoisted(() => ({
  getCard: vi.fn(),
  listLabels: vi.fn(),
  updateCard: vi.fn(),
  deleteCard: vi.fn(),
  createLabel: vi.fn(),
  createChecklistItem: vi.fn(),
  updateChecklistItem: vi.fn(),
  deleteChecklistItem: vi.fn(),
  listComments: vi.fn(),
  createComment: vi.fn(),
  updateComment: vi.fn(),
  deleteComment: vi.fn(),
  getToken: vi.fn(() => "jwt"),
  me: vi.fn(),
  clearToken: vi.fn(),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, ...api };
});

const ME = { id: 1, email: "ada@example.com", display_name: "Ada", created_at: "" };
const OPEN_CARD = card({
  id: 100,
  title: "Write tests",
  description: "Cover the modal",
  priority: "high",
  due_date: "2026-03-04T00:00:00Z",
  assignee_id: 2,
  parent_card_id: 101,
  labels: [{ id: 5, board_id: 1, name: "bug" }],
  checklist_items: [
    { id: 1, card_id: 100, content: "Write it", completed: true, position: 0 },
    { id: 2, card_id: 100, content: "Run it", completed: false, position: 1 },
  ],
});
const LABELS = [
  { id: 5, board_id: 1, name: "bug" },
  { id: 6, board_id: 1, name: "ui" },
];
const COMMENTS = [
  { id: 1, card_id: 100, author: { id: 1, display_name: "Ada" }, content: "Mine", created_at: "2026-01-01T10:00:00Z", updated_at: "2026-01-01T10:00:00Z" },
  { id: 2, card_id: 100, author: { id: 2, display_name: "Grace" }, content: "Theirs", created_at: "2026-01-01T11:00:00Z", updated_at: "2026-01-01T12:00:00Z" },
];

function renderModal(onClose = vi.fn(), onChanged = vi.fn().mockResolvedValue(undefined)) {
  render(
    <AuthProvider>
      <CardModal cardId={100} columns={columns} members={members} cards={cards} onClose={onClose} onChanged={onChanged} />
    </AuthProvider>,
  );
  return { onClose, onChanged };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.me.mockResolvedValue(ME);
  api.getCard.mockResolvedValue(OPEN_CARD);
  api.listLabels.mockResolvedValue(LABELS);
  api.listComments.mockResolvedValue(COMMENTS);
});

describe("CardModal fields", () => {
  test("opens with the card's data, including parent, labels and assignee", async () => {
    renderModal();

    const dialog = await screen.findByRole("dialog", { name: "Write tests" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe("Write tests");
    expect((screen.getByLabelText("Description") as HTMLTextAreaElement).value).toBe("Cover the modal");
    expect((screen.getByLabelText("Column") as HTMLSelectElement).value).toBe("10");
    expect((screen.getByLabelText("Priority") as HTMLSelectElement).value).toBe("high");
    expect((screen.getByLabelText("Due date") as HTMLInputElement).value).toBe("2026-03-04");
    expect((screen.getByLabelText("Assignee") as HTMLSelectElement).value).toBe("2");
    await screen.findByLabelText("ui");
    expect((screen.getByLabelText("bug") as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText("ui") as HTMLInputElement).checked).toBe(false);
    expect(screen.getByText("Ship it")).toBeDefined(); // parent title (card 101)
    expect(document.activeElement).toBe(screen.getByLabelText("Title"));
  });

  test("saving a field change PATCHes only that field, refetches and closes", async () => {
    api.updateCard.mockResolvedValue({ ...OPEN_CARD, title: "Write more tests" });
    const { onClose, onChanged } = renderModal();
    await screen.findByRole("dialog");

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: " Write more tests " } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(api.updateCard).toHaveBeenCalledWith(100, { title: "Write more tests" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(onChanged).toHaveBeenCalled();
  });

  test("changing several fields sends them together in the PATCH shape", async () => {
    api.updateCard.mockResolvedValue(OPEN_CARD);
    renderModal();
    await screen.findByRole("dialog");
    await screen.findByLabelText("ui");

    fireEvent.change(screen.getByLabelText("Column"), { target: { value: "12" } });
    fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "low" } });
    fireEvent.change(screen.getByLabelText("Due date"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Assignee"), { target: { value: "" } });
    fireEvent.click(screen.getByLabelText("ui"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(api.updateCard).toHaveBeenCalledWith(100, {
        column_id: 12,
        priority: "low",
        due_date: null,
        assignee_id: null,
        label_ids: [5, 6],
      }),
    );
  });

  test("creating a new label adds and selects it", async () => {
    api.createLabel.mockResolvedValue({ id: 7, board_id: 1, name: "docs" });
    renderModal();
    await screen.findByRole("dialog");

    fireEvent.change(screen.getByLabelText("New label name"), { target: { value: "docs" } });
    fireEvent.click(screen.getByRole("button", { name: "Add label" }));

    expect(await screen.findByLabelText("docs")).toBeDefined();
    expect(api.createLabel).toHaveBeenCalledWith(1, "docs");
    expect((screen.getByLabelText("docs") as HTMLInputElement).checked).toBe(true);
  });

  test("saving with no changes just closes", async () => {
    const { onClose } = renderModal();
    await screen.findByRole("dialog");

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(api.updateCard).not.toHaveBeenCalled();
  });

  test("delete asks for confirmation, calls the API and closes", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    api.deleteCard.mockResolvedValue(undefined);
    const { onClose, onChanged } = renderModal();
    await screen.findByRole("dialog");

    fireEvent.click(screen.getByRole("button", { name: "Delete card" }));

    await waitFor(() => expect(api.deleteCard).toHaveBeenCalledWith(100));
    expect(onChanged).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  test("Escape closes the modal", async () => {
    const { onClose } = renderModal();
    await screen.findByRole("dialog");

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onClose).toHaveBeenCalled();
  });

  test("diffCard maps the draft to the PATCH body", () => {
    const base = card({ id: 1, title: "a", due_date: null, labels: [] });
    const draft = { title: "a", description: "", column_id: 10, priority: "medium" as const, due_date: "", assignee_id: null, label_ids: [] };
    expect(diffCard(base, draft)).toEqual({});
    expect(diffCard(base, { ...draft, due_date: "2026-05-06" })).toEqual({ due_date: "2026-05-06T00:00:00Z" });
  });
});

describe("CardModal checklist", () => {
  test("shows the completed count and toggles an item", async () => {
    api.updateChecklistItem.mockResolvedValue({ id: 2, card_id: 100, content: "Run it", completed: true, position: 1 });
    api.getCard
      .mockResolvedValueOnce(OPEN_CARD)
      .mockResolvedValue({ ...OPEN_CARD, checklist_items: OPEN_CARD.checklist_items.map((i) => ({ ...i, completed: true })) });
    const { onChanged } = renderModal();
    await screen.findByRole("dialog");
    expect(screen.getByTestId("checklist-count").textContent).toBe("1/2 done");

    fireEvent.click(screen.getByLabelText("Toggle Run it"));

    await waitFor(() => expect(api.updateChecklistItem).toHaveBeenCalledWith(2, { completed: true }));
    await waitFor(() => expect(screen.getByTestId("checklist-count").textContent).toBe("2/2 done"));
    expect(onChanged).toHaveBeenCalled();
  });

  test("add, edit, reorder and remove items call the right endpoints", async () => {
    api.createChecklistItem.mockResolvedValue({});
    api.updateChecklistItem.mockResolvedValue({});
    api.deleteChecklistItem.mockResolvedValue(undefined);
    renderModal();
    await screen.findByRole("dialog");

    fireEvent.change(screen.getByLabelText("New checklist item"), { target: { value: " Ship it " } });
    fireEvent.submit(screen.getByLabelText("New checklist item").closest("form")!);
    await waitFor(() => expect(api.createChecklistItem).toHaveBeenCalledWith(100, "Ship it"));

    fireEvent.click(screen.getByRole("button", { name: "Run it" }));
    const edit = screen.getByLabelText("Edit Run it");
    fireEvent.change(edit, { target: { value: "Run them" } });
    fireEvent.keyDown(edit, { key: "Enter" });
    await waitFor(() => expect(api.updateChecklistItem).toHaveBeenCalledWith(2, { content: "Run them" }));

    fireEvent.click(screen.getByRole("button", { name: "Move Run it up" }));
    await waitFor(() => expect(api.updateChecklistItem).toHaveBeenCalledWith(2, { position: 0 }));
    expect((screen.getByRole("button", { name: "Move Write it up" }) as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Remove Write it" }));
    await waitFor(() => expect(api.deleteChecklistItem).toHaveBeenCalledWith(1));
  });
});

describe("CardModal comments", () => {
  test("lists comments with author and time; edit/delete only on own comments", async () => {
    renderModal();
    const section = await screen.findByRole("region", { name: "Comments" });

    expect(await within(section).findByText("Mine")).toBeDefined();
    expect(within(section).getByText("Theirs")).toBeDefined();
    expect(within(section).getByText("Ada")).toBeDefined();
    expect(within(section).getByText("Grace")).toBeDefined();
    expect(within(section).getByText("(edited)")).toBeDefined();
    expect(within(section).getAllByRole("button", { name: "Edit comment" })).toHaveLength(1);
    expect(section.querySelectorAll("time")).toHaveLength(2);
  });

  test("posting a comment calls the API and shows it", async () => {
    api.createComment.mockResolvedValue({});
    api.listComments
      .mockResolvedValueOnce(COMMENTS)
      .mockResolvedValue([...COMMENTS, { id: 3, card_id: 100, author: { id: 1, display_name: "Ada" }, content: "New one", created_at: "2026-01-02T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" }]);
    renderModal();
    const section = await screen.findByRole("region", { name: "Comments" });
    await within(section).findByText("Mine");

    fireEvent.change(screen.getByLabelText("New comment"), { target: { value: "  New one  " } });
    fireEvent.click(screen.getByRole("button", { name: "Post comment" }));

    await waitFor(() => expect(api.createComment).toHaveBeenCalledWith(100, "New one"));
    expect(await within(section).findByText("New one")).toBeDefined();
    expect((screen.getByLabelText("New comment") as HTMLTextAreaElement).value).toBe("");
  });

  test("editing and deleting an own comment", async () => {
    api.updateComment.mockResolvedValue({});
    api.deleteComment.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderModal();
    const section = await screen.findByRole("region", { name: "Comments" });
    await within(section).findByText("Mine");

    fireEvent.click(within(section).getByRole("button", { name: "Edit comment" }));
    fireEvent.change(screen.getByLabelText("Edit comment text"), { target: { value: "Mine, edited" } });
    fireEvent.click(screen.getByRole("button", { name: "Save comment" }));
    await waitFor(() => expect(api.updateComment).toHaveBeenCalledWith(1, "Mine, edited"));

    fireEvent.click(within(section).getByRole("button", { name: "Delete comment" }));
    await waitFor(() => expect(api.deleteComment).toHaveBeenCalledWith(1));
  });
});
