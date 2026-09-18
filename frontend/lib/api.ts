/**
 * Typed client for the FastAPI backend.
 *
 * The base URL comes from NEXT_PUBLIC_API_URL (see .env.example). The JWT is
 * kept in localStorage under TOKEN_KEY and attached as a bearer header; a
 * 401 means the token is gone (expired, or JWT_SECRET rotated) and the auth
 * provider sends the user back to /login.
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ?? "http://127.0.0.1:8000";
export const TOKEN_KEY = "mini-kanban.token";

export type User = {
  id: number;
  email: string;
  display_name: string;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  user: User;
};

export type Board = {
  id: number;
  name: string;
  owner_id: number;
  role: "owner" | "member";
  created_at: string;
  updated_at: string;
};

export type Column = {
  id: number;
  board_id: number;
  name: string;
  position: number;
  created_at: string;
};

export type BoardDetail = Board & { columns: Column[] };

/** A non-2xx response. `detail` is FastAPI's error body when it is a string. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

async function request<T>(path: string, method: Method = "GET", body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await errorDetail(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      // Pydantic validation errors: [{loc, msg, ...}]
      return data.detail
        .map((item: { loc?: unknown[]; msg?: string }) =>
          [item.loc?.slice(1).join("."), item.msg].filter(Boolean).join(": "),
        )
        .join("; ");
    }
  } catch {
    // not JSON
  }
  return `Request failed with status ${response.status}`;
}

// --- auth -------------------------------------------------------------------

export function signup(body: { email: string; password: string; display_name: string }) {
  return request<TokenResponse>("/auth/signup", "POST", body);
}

export function login(body: { email: string; password: string }) {
  return request<TokenResponse>("/auth/login", "POST", body);
}

export function me() {
  return request<User>("/auth/me");
}

// --- boards -----------------------------------------------------------------

export function listBoards() {
  return request<Board[]>("/boards");
}

export function createBoard(name: string) {
  return request<BoardDetail>("/boards", "POST", { name });
}

export function getBoard(id: number) {
  return request<BoardDetail>(`/boards/${id}`);
}

export function renameBoard(id: number, name: string) {
  return request<Board>(`/boards/${id}`, "PATCH", { name });
}

export function deleteBoard(id: number) {
  return request<void>(`/boards/${id}`, "DELETE");
}

// --- columns ----------------------------------------------------------------

export function createColumn(boardId: number, name: string) {
  return request<Column>(`/boards/${boardId}/columns`, "POST", { name });
}

export function updateColumn(id: number, body: { name?: string; position?: number }) {
  return request<Column>(`/columns/${id}`, "PATCH", body);
}

export function deleteColumn(id: number) {
  return request<void>(`/columns/${id}`, "DELETE");
}

// --- cards ------------------------------------------------------------------

export type Priority = "low" | "medium" | "high";

export type Label = { id: number; board_id: number; name: string };

export type ChecklistItem = {
  id: number;
  card_id: number;
  content: string;
  completed: boolean;
  position: number;
};

export type Card = {
  id: number;
  board_id: number;
  column_id: number;
  parent_card_id: number | null;
  title: string;
  description: string;
  priority: Priority;
  due_date: string | null;
  assignee_id: number | null;
  position: number;
  created_at: string;
  updated_at: string;
  labels: Label[];
  checklist_items: ChecklistItem[];
};

export type CardFilters = {
  q?: string;
  column_id?: number | null;
  priority?: Priority | "";
  assignee_id?: number | null;
};

/** The query string for GET /boards/{id}/cards; blank filters are omitted. */
export function buildCardQuery(filters: CardFilters): string {
  const params = new URLSearchParams();
  const q = filters.q?.trim();
  if (q) params.set("q", q);
  if (filters.column_id != null) params.set("column_id", String(filters.column_id));
  if (filters.priority) params.set("priority", filters.priority);
  if (filters.assignee_id != null) params.set("assignee_id", String(filters.assignee_id));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function listCards(boardId: number, filters: CardFilters = {}) {
  return request<Card[]>(`/boards/${boardId}/cards${buildCardQuery(filters)}`);
}

export type CardCreate = {
  title: string;
  column_id: number;
  description?: string;
  priority?: Priority;
  due_date?: string | null;
  assignee_id?: number | null;
  parent_card_id?: number | null;
  label_ids?: number[];
  position?: number;
};

export function createCard(boardId: number, body: CardCreate) {
  return request<Card>(`/boards/${boardId}/cards`, "POST", body);
}

export type CardUpdate = Partial<CardCreate>;

export function updateCard(id: number, body: CardUpdate) {
  return request<Card>(`/cards/${id}`, "PATCH", body);
}

export function deleteCard(id: number) {
  return request<void>(`/cards/${id}`, "DELETE");
}

export function listLabels(boardId: number) {
  return request<Label[]>(`/boards/${boardId}/labels`);
}

// --- members and invites ----------------------------------------------------

export type Member = {
  user_id: number;
  email: string;
  display_name: string;
  role: "owner" | "member";
  created_at: string;
};

export type Invite = { board_id: number; invite_token: string; invite_path: string };

export function listMembers(boardId: number) {
  return request<Member[]>(`/boards/${boardId}/members`);
}

export function getInvite(boardId: number) {
  return request<Invite>(`/boards/${boardId}/invite`, "POST");
}

export function inviteByEmail(boardId: number, email: string) {
  return request<Member>(`/boards/${boardId}/members`, "POST", { email });
}

export function removeMember(boardId: number, userId: number) {
  return request<void>(`/boards/${boardId}/members/${userId}`, "DELETE");
}

export function joinByInvite(token: string) {
  return request<{ board: Board; joined: boolean }>(`/invite/${encodeURIComponent(token)}/join`, "POST");
}

// --- dashboard --------------------------------------------------------------

export type Dashboard = {
  board_id: number;
  total: number;
  by_column: { column_id: number; name: string; position: number; count: number }[];
  overdue: number;
  done: number;
  progress_percent: number;
};

export function getDashboard(boardId: number) {
  return request<Dashboard>(`/boards/${boardId}/dashboard`);
}
