import { beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { AiPanel, estimateLine } from "@/components/card/AiPanel";
import { BoardView } from "@/components/board/BoardView";
import { AuthProvider } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { board, card, cards, members } from "./fixtures";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const api = vi.hoisted(() => ({
  aiImprove: vi.fn(),
  aiPrioritize: vi.fn(),
  aiEstimate: vi.fn(),
  aiSummarize: vi.fn(),
  aiBreakdown: vi.fn(),
  aiApplyBreakdown: vi.fn(),
  aiCreateTask: vi.fn(),
  updateCard: vi.fn(),
  createCard: vi.fn(),
  getBoard: vi.fn(),
  listCards: vi.fn(),
  listMembers: vi.fn(),
  listLabels: vi.fn(),
  getToken: vi.fn(() => null),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, ...api };
});

const CARD = card({ id: 100, title: "Fix login", description: "Users land on /404" });

function renderPanel() {
  const onApplied = vi.fn().mockResolvedValue(undefined);
  render(<AiPanel card={CARD} onApplied={onApplied} />);
  return { onApplied };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AiPanel: Approve writes, Discard does not", () => {
  test("Prioritize → Approve PATCHes the (editable) proposed priority", async () => {
    api.aiPrioritize.mockResolvedValue({ text: "Due soon.", priority: "high" });
    api.updateCard.mockResolvedValue(CARD);
    const { onApplied } = renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Prioritize" }));
    const preview = await screen.findByRole("region", { name: "AI preview" });
    expect(within(preview).getByText("Due soon.")).toBeDefined();
    expect((within(preview).getByLabelText("Proposed priority") as HTMLSelectElement).value).toBe("high");
    expect(api.updateCard).not.toHaveBeenCalled();

    fireEvent.click(within(preview).getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(api.updateCard).toHaveBeenCalledWith(100, { priority: "high" }));
    expect(onApplied).toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole("region", { name: "AI preview" })).toBeNull());
  });

  test("Improve → Discard changes nothing and closes the preview", async () => {
    api.aiImprove.mockResolvedValue({ text: "Sharper.", title: "Fix login redirect", description: "Steps…" });
    const { onApplied } = renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Improve" }));
    const preview = await screen.findByRole("region", { name: "AI preview" });
    expect((within(preview).getByLabelText("Proposed title") as HTMLInputElement).value).toBe("Fix login redirect");

    fireEvent.click(within(preview).getByRole("button", { name: "Discard" }));

    expect(screen.queryByRole("region", { name: "AI preview" })).toBeNull();
    expect(api.updateCard).not.toHaveBeenCalled();
    expect(api.aiApplyBreakdown).not.toHaveBeenCalled();
    expect(onApplied).not.toHaveBeenCalled();
  });

  test("Improve → edit the proposal → Approve PATCHes title and description", async () => {
    api.aiImprove.mockResolvedValue({ text: "Sharper.", title: "Fix login redirect", description: "Steps…" });
    api.updateCard.mockResolvedValue(CARD);
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Improve" }));
    const preview = await screen.findByRole("region", { name: "AI preview" });
    fireEvent.change(within(preview).getByLabelText("Proposed title"), { target: { value: "Fix the login redirect" } });
    fireEvent.click(within(preview).getByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(api.updateCard).toHaveBeenCalledWith(100, { title: "Fix the login redirect", description: "Steps…" }),
    );
  });

  test("Estimate → Approve appends the estimate line to the description", async () => {
    const estimate = { text: "Two files.", size: "Small" as const, time_estimate: "2 hours" };
    api.aiEstimate.mockResolvedValue(estimate);
    api.updateCard.mockResolvedValue(CARD);
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Estimate effort" }));
    const preview = await screen.findByRole("region", { name: "AI preview" });
    expect(within(preview).getByText("Small")).toBeDefined();
    fireEvent.click(within(preview).getByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(api.updateCard).toHaveBeenCalledWith(100, {
        description: `Users land on /404\n\n${estimateLine(estimate)}`,
      }),
    );
    expect(estimateLine(estimate)).toBe("Estimate: Small (2 hours)");
  });

  test("Summarize is read-only: text, a Close button and no Approve", async () => {
    api.aiSummarize.mockResolvedValue({ text: "Login sends users to the wrong page." });
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Summarize" }));
    const preview = await screen.findByRole("region", { name: "AI preview" });

    expect(within(preview).getByText("Login sends users to the wrong page.")).toBeDefined();
    expect(within(preview).queryByRole("button", { name: "Approve" })).toBeNull();
    fireEvent.click(within(preview).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("region", { name: "AI preview" })).toBeNull();
    expect(api.updateCard).not.toHaveBeenCalled();
  });

  test("Break down → edit the list → Approve posts the edited tasks to breakdown/apply", async () => {
    api.aiBreakdown.mockResolvedValue({
      text: "Three steps.",
      tasks: [
        { title: "Write the migration", description: "Add the column." },
        { title: "Update the API", description: "" },
        { title: "Ship it", description: "" },
      ],
    });
    api.aiApplyBreakdown.mockResolvedValue([]);
    const { onApplied } = renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Break down" }));
    const preview = await screen.findByRole("region", { name: "AI preview" });
    fireEvent.change(within(preview).getByLabelText("Task 1 title"), { target: { value: "Write the DB migration" } });
    fireEvent.click(within(preview).getByRole("button", { name: "Remove task 2" }));
    fireEvent.click(within(preview).getByRole("button", { name: "Add task" }));
    fireEvent.change(within(preview).getByLabelText("Task 3 title"), { target: { value: "Announce" } });
    expect(api.aiApplyBreakdown).not.toHaveBeenCalled();

    fireEvent.click(within(preview).getByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(api.aiApplyBreakdown).toHaveBeenCalledWith(100, [
        { title: "Write the DB migration", description: "Add the column." },
        { title: "Ship it", description: "" },
        { title: "Announce", description: "" },
      ]),
    );
    expect(onApplied).toHaveBeenCalled();
  });

  test("Break down → Discard never calls apply", async () => {
    api.aiBreakdown.mockResolvedValue({ text: "x", tasks: [{ title: "a", description: "" }] });
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Break down" }));
    const preview = await screen.findByRole("region", { name: "AI preview" });
    fireEvent.click(within(preview).getByRole("button", { name: "Discard" }));

    expect(api.aiApplyBreakdown).not.toHaveBeenCalled();
  });

  test("an AI error is shown and nothing is written", async () => {
    api.aiPrioritize.mockRejectedValue(new ApiError(503, "AI is not configured: set OPENAI_API_KEY or GEMINI_API_KEY"));
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Prioritize" }));

    expect(await screen.findByText("AI is not configured: set OPENAI_API_KEY or GEMINI_API_KEY")).toBeDefined();
    expect(screen.queryByRole("region", { name: "AI preview" })).toBeNull();
    expect(api.updateCard).not.toHaveBeenCalled();
  });
});

describe("New task from text: preview then create", () => {
  const PROPOSAL = {
    text: "A login fix, urgent, due Friday.",
    title: "Fix login redirect",
    description: "Users land on /404 after login.",
    priority: "high" as const,
    due_date: "2026-09-25T00:00:00Z",
  };

  beforeEach(() => {
    api.getBoard.mockResolvedValue(board);
    api.listCards.mockResolvedValue(cards);
    api.listMembers.mockResolvedValue(members);
    api.listLabels.mockResolvedValue([]);
  });

  test("the proposal opens in the modal for editing and Save creates the card via the card POST", async () => {
    api.aiCreateTask.mockResolvedValue(PROPOSAL);
    api.createCard.mockResolvedValue(card({ id: 200 }));
    render(
      <AuthProvider>
        <BoardView boardId={1} />
      </AuthProvider>,
    );
    await screen.findByRole("heading", { level: 1, name: "Roadmap" });

    fireEvent.change(screen.getByLabelText("New task from text"), { target: { value: " Fix the login redirect, urgent, by Friday " } });
    fireEvent.click(screen.getByRole("button", { name: "Propose" }));

    const dialog = await screen.findByRole("dialog", { name: "New card" });
    expect(api.aiCreateTask).toHaveBeenCalledWith(1, "Fix the login redirect, urgent, by Friday");
    expect(api.createCard).not.toHaveBeenCalled(); // preview only
    expect(within(dialog).getByText(PROPOSAL.text)).toBeDefined();
    expect((within(dialog).getByLabelText("Title") as HTMLInputElement).value).toBe("Fix login redirect");
    expect((within(dialog).getByLabelText("Priority") as HTMLSelectElement).value).toBe("high");
    expect((within(dialog).getByLabelText("Due date") as HTMLInputElement).value).toBe("2026-09-25");
    expect((within(dialog).getByLabelText("Column") as HTMLSelectElement).value).toBe("10"); // first column

    fireEvent.change(within(dialog).getByLabelText("Column"), { target: { value: "11" } });
    fireEvent.change(within(dialog).getByLabelText("Title"), { target: { value: "Fix the login redirect" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create card" }));

    await waitFor(() =>
      expect(api.createCard).toHaveBeenCalledWith(1, {
        title: "Fix the login redirect",
        description: "Users land on /404 after login.",
        column_id: 11,
        priority: "high",
        due_date: "2026-09-25T00:00:00Z",
        assignee_id: null,
        label_ids: [],
      }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(api.listCards).toHaveBeenCalledTimes(2)); // board refetched
  });

  test("Discard in the proposal modal creates nothing", async () => {
    api.aiCreateTask.mockResolvedValue(PROPOSAL);
    render(
      <AuthProvider>
        <BoardView boardId={1} />
      </AuthProvider>,
    );
    await screen.findByRole("heading", { level: 1, name: "Roadmap" });

    fireEvent.change(screen.getByLabelText("New task from text"), { target: { value: "anything" } });
    fireEvent.click(screen.getByRole("button", { name: "Propose" }));
    const dialog = await screen.findByRole("dialog", { name: "New card" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Discard" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.createCard).not.toHaveBeenCalled();
  });
});
