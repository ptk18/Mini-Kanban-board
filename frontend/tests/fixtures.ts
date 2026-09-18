import type { BoardDetail, Card, Column, Member } from "@/lib/api";

export const columns: Column[] = [
  { id: 10, board_id: 1, name: "To Do", position: 0, created_at: "2026-01-01T00:00:00Z" },
  { id: 11, board_id: 1, name: "In Progress", position: 1, created_at: "2026-01-01T00:00:00Z" },
  { id: 12, board_id: 1, name: "Done", position: 2, created_at: "2026-01-01T00:00:00Z" },
];

export const board: BoardDetail = {
  id: 1,
  name: "Roadmap",
  owner_id: 1,
  role: "owner",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  columns,
};

export const members: Member[] = [
  { user_id: 1, email: "ada@example.com", display_name: "Ada", role: "owner", created_at: "2026-01-01T00:00:00Z" },
  { user_id: 2, email: "grace@example.com", display_name: "Grace", role: "member", created_at: "2026-01-02T00:00:00Z" },
];

export function card(overrides: Partial<Card>): Card {
  return {
    id: 100,
    board_id: 1,
    column_id: 10,
    parent_card_id: null,
    title: "Card",
    description: "",
    priority: "medium",
    due_date: null,
    assignee_id: null,
    position: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    labels: [],
    checklist_items: [],
    ...overrides,
  };
}

export const cards: Card[] = [
  card({ id: 100, column_id: 10, title: "Write tests", priority: "high", due_date: "2020-01-01T00:00:00Z", assignee_id: 2, labels: [{ id: 5, board_id: 1, name: "bug" }] }),
  card({ id: 101, column_id: 10, title: "Ship it", priority: "low", position: 1 }),
  card({ id: 102, column_id: 12, title: "Set up CI", priority: "medium", due_date: "2020-01-01T00:00:00Z" }),
];
