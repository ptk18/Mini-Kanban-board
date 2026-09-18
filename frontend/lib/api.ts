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
