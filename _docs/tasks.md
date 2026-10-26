# Mini Kanban Board — Task Backlog

Derived from `_docs/plan.md`. Each task is one GitHub issue (the number in the heading is the issue number) and is sized for one working session. Shared context every task assumes:

- Repo layout: `backend/` (FastAPI, Python, SQLAlchemy, SQLite, pytest) and `frontend/` (Next.js, TypeScript, Tailwind CSS).
- Backend code lives under `backend/app/` with `models/`, `schemas/`, `routers/`, `services/`; tests under `backend/tests/`.
- Auth is JWT (email/password). Board roles are `owner` and `member`. Boards are private to owner + members.
- AI provider is Google Gemini. AI endpoints only return suggestions; the user must approve before anything is written.
- Deployment is local only. No Alembic; tables are created directly from SQLAlchemy models.
- No WebSockets: the frontend refetches after its own mutations and on tab focus (`plan.md` §5).
- No activity log, no board-level AI assistant, no profile/settings page (`plan.md` §18). The `Activity` model exists but is unused.

The backlog was reduced from 38 to 19 issues on 2026-09-18. Merged issues name the issues they absorbed; the absorbed issues are closed on GitHub with a link back here.

---

# Completed

## 1. Set up the backend project with a passing test
Goal: An empty FastAPI project that runs and has one green pytest test.
Description: Create `backend/` with a `pyproject.toml` (or `requirements.txt`) pinning FastAPI, Uvicorn, SQLAlchemy, pytest and httpx. Add `backend/app/main.py` exposing a `GET /health` endpoint returning `{"status": "ok"}`, and `backend/tests/test_health.py` that calls it through FastAPI's `TestClient` and asserts the response. Document the install and `pytest` commands in `backend/README.md`.

## 2. Set up the frontend project with a passing test
Goal: An empty Next.js + TypeScript + Tailwind app with one green component test.
Description: Scaffold `frontend/` with Next.js (App Router), TypeScript and Tailwind CSS configured for a dark theme by default (dark background, light text on the root layout). Add a test runner (Vitest + React Testing Library) and one test that renders the home page and asserts on a heading. Document `npm run dev` and `npm test` in `frontend/README.md`.

## 3. Define the database layer and SQLAlchemy models
Goal: All core tables exist as SQLAlchemy models backed by a SQLite file.
Description: Add `backend/app/database.py` with the engine, session factory, and a `get_db` dependency; the SQLite path should come from an environment variable with a sensible default. Implement models for User, Board, BoardMember, Column, Card, Label, CardLabel, ChecklistItem, Comment and Activity using the fields listed in `_docs/plan.md` §13 (including `position` on Column/Card/ChecklistItem, nullable `parent_card_id` and `assignee_id` on Card). Create tables on app startup (no Alembic) and add a test that creates the schema in an in-memory SQLite database and inserts one row per model.

## 4. Implement email/password authentication with JWT
Goal: Users can sign up, log in, and fetch their own profile with a bearer token.
Description: Add `POST /auth/signup`, `POST /auth/login` and `GET /auth/me` backed by the User model (assumes task 3). Hash passwords (e.g. bcrypt via passlib), issue JWTs signed with a secret from an environment variable, and provide a `get_current_user` dependency that other routers can reuse. Cover with tests: successful signup, duplicate email rejected, wrong password rejected, `/auth/me` with and without a valid token.

## 9. Implement checklists on cards
Goal: Each card can have a flat list of checklist items that can be added, edited, toggled, reordered and removed.
Description: Add endpoints under `/cards/{card_id}/checklist` for creating items, and `PATCH/DELETE /checklist/{item_id}` for editing content, toggling `completed`, and reordering by `position`. No nesting. The card detail response should include its checklist items in order. Test add, edit, toggle, reorder and delete, plus rejection for users who are not members of the card's board.

## 10. Implement comments on cards
Goal: Board members can post, read, edit and delete plain-text comments on cards.
Description: Add `POST/GET /cards/{card_id}/comments` and `PATCH/DELETE /comments/{comment_id}`. Each comment records author, content, created and updated timestamps; responses should include the author's display name. Only the author may edit or delete their own comment. Test posting, listing in chronological order, editing by the author, and rejection when a different member tries to edit.

---

# Backend

## 5. Implement board CRUD, permissions and column management (absorbs #6)
Goal: Authenticated users can create, list, view, rename and delete boards they belong to, and members can manage a board's columns.
Description: Add `GET/POST /boards`, `GET/PATCH/DELETE /boards/{board_id}` (assumes models and auth from tasks 3–4). Creating a board also creates a BoardMember row with role `owner` and the three default columns "To Do", "In Progress", "Done". Only members can view/rename; only the owner can delete. Add `POST /boards/{board_id}/columns`, `PATCH /columns/{column_id}` (name and/or position) and `DELETE /columns/{column_id}`. Deleting a column should either be refused when it still holds cards or move them to the first remaining column — pick one and document it in the router docstring. Include a `position` reorder strategy that keeps positions contiguous. Tests: non-member gets 404/403, member cannot delete a board, owner can, listing returns only the user's boards; column create/rename/reorder/delete and the rule that non-members are rejected.

## 7. Implement card CRUD, card movement and labels (absorbs #8)
Goal: Board members can create, read, update, move and delete cards, and attach any number of board labels to them.
Description: Add `POST/GET /boards/{board_id}/cards`, `GET/PATCH/DELETE /cards/{card_id}` (assumes boards and columns exist). Cards carry title, description, column, priority, due date, assignee, optional parent card, and a manual `position` within their column. `PATCH` must support moving a card to another column and reordering within a column while keeping positions consistent. Add label endpoints per board (`/boards/{board_id}/labels` create/list/rename/delete) and let the card `PATCH` accept `label_ids`; deleting a label removes it from all cards. Tests: create, update, move between columns, reorder, delete, a card cannot reference a parent on a different board, attaching two labels then detaching one, and label deletion cascading.

## 11. Implement board invitations and member management, backend and UI (absorbs #30)
Goal: Owners can share a permanent invite link and manage members; invitees can join from the browser.
Description: Backend: an endpoint for the owner to fetch/generate the board's permanent invite token, an endpoint an authenticated user calls with that token to join as `member`, endpoints to list and remove members (owner only; the owner cannot be removed), and invite-by-email that adds an existing user directly. Frontend (assumes the board page from task 23): a board "Members" panel listing members with roles, letting the owner copy the invite link, invite by email and remove members; and an `/invite/[token]` page that, for a logged-in user, calls the join endpoint and redirects to the board (redirecting to login first if needed). Tests: joining via a valid token, invalid token rejected, non-owner cannot remove members, joining twice is idempotent; and a frontend test for the invite page's join-then-redirect behaviour.

## 13. Implement the dashboard endpoint and page (absorbs #31)
Goal: A per-board dashboard shows total tasks, tasks by status, overdue tasks and progress percentage.
Description: Add `GET /boards/{board_id}/dashboard` returning total card count, counts grouped by column, overdue count (`due_date < now` and column is not "Done"), and progress percentage (`cards in Done / total * 100`, 0 when there are no cards). Decide how "Done" is identified (by column name match) and document it. Add `/boards/[id]/dashboard` that renders the four metrics with a simple progress bar, linked from the board header. No charts, trends or timelines. Tests: each metric with a small fixture board including the zero-card case, and a frontend render test from mocked data including the zero-task state.

## 14. Implement card search and filtering, backend and UI (absorbs #28)
Goal: Users can search cards and filter by status, priority and assignee from the board.
Description: Extend `GET /boards/{board_id}/cards` with query parameters `q` (case-insensitive match on title or description), `column_id`, `priority` and `assignee_id`; filters combine with AND. No label or due-date filters, no saved filters. Add a compact toolbar above the board with a search input and the three filter dropdowns, pass the values as query parameters, re-render the board, and show an active-filter count with a clear button. Tests: search on title vs description, each filter individually and a combination; a frontend test that the query string is built correctly from selected filters.

## 16. Integrate Gemini and implement the single-card AI actions
Goal: The Improve, Prioritize, Estimate effort and Summarize actions return previews without changing the card.
Description: Add a Gemini client in `backend/app/services/ai.py` behind a small interface so tests can inject a fake. Implement `POST /ai/card/{card_id}/improve|prioritize|estimate|summarize` using only the current card's fields as context; each returns natural-language text plus, where relevant, structured proposed values (priority; size Small/Medium/Large and a time estimate). Nothing is written to the database. Test each endpoint with the fake client and verify the card is unchanged afterwards.

## 17. Implement AI task breakdown and natural-language task creation with approval (absorbs #18)
Goal: A card can be broken into proposed child cards, and a sentence can become a proposed card, with nothing written until the user approves.
Description: Assumes the Gemini client from task 16. Add `POST /ai/card/{card_id}/breakdown` returning a list of proposed child tasks (title, description), and `POST /ai/card/{card_id}/breakdown/apply` that accepts the user-edited list and creates child cards with `parent_card_id` set, in the same column as the parent. Add `POST /ai/create-task` taking a board id and free text and returning a proposed card (title, description, priority, due date if mentioned) without saving it; creation happens through the normal card `POST` once the user approves, so no extra write endpoint is needed — document that contract in the router. Tests: breakdown preview creates nothing, apply creates the given children with the correct parent and board, create-task preview returns the proposal and no card exists afterwards.

## 20. Create the seed data script, top-level README and team docs (absorbs #36, #38)
Goal: One command populates a demo board, and a newcomer can run the whole app and follow the team's standards from the docs.
Description: Add `backend/scripts/seed.py` that creates two or three demo users and an "Insurance Policy Automation" board with columns Backlog, To Do, In Progress, Review, Done, populated with cards spanning priorities, due dates (some overdue), labels, assignees, checklists, comments and at least one parent/child pair. The script must be idempotent; add a test that runs it against an in-memory database and asserts on counts. Write the root `README.md` covering prerequisites, environment variables (backend secret, database path, CORS origins, Gemini API key, frontend API URL), starting both apps, running the seed and both test suites, plus a short architecture overview; verify it from a clean checkout. Fill in `_docs/design-system.md` (dark-only theme tokens from task 2, font stack, spacing/typography for cards and columns, `plan.md` §10 characteristics) and `_docs/testing-guidelines.md` (where tests live, how to run them, RTL query conventions, the approach to user-flow tests), checking every statement against the code.

---

# Frontend

## 21. Build the frontend API client, CORS, auth pages and board list (absorbs #22, #37)
Goal: Users can sign up, log in, log out, and see and manage their boards.
Description: Backend: register `CORSMiddleware` in `backend/app/main.py` with origins from `CORS_ORIGINS` (default `http://localhost:3000`), allowing `Authorization`/`Content-Type` and all API methods; test that an `Origin: http://localhost:3000` request gets `access-control-allow-origin`. Frontend: a typed API client that reads the backend URL from an environment variable, attaches the JWT from storage and exposes `signup`, `login`, `me`; Login and Sign up pages in the dark minimal style, an auth provider, a route guard that redirects unauthenticated users, and a logout button in the app header. Add a `/boards` page listing the user's boards from `GET /boards`, with a create-board form, inline rename, and an owner-only delete with confirmation; clicking a board navigates to `/boards/[id]`. Tests: login form validation and successful submit with a mocked client; board list renders from mocked data and exercises create.

## 23. Build the board page with columns, cards and column management (absorbs #27)
Goal: The board screen shows columns and cards, supports creating a card, and lets members manage columns.
Description: Add `/boards/[id]` that loads the board, its columns and cards and renders them as horizontal columns of compact cards showing title, priority, due date, labels and assignee. Include an "add card" input at the bottom of each column and a status dropdown on each card for moving it between columns. Add an "add column" control at the end of the board, inline rename on column headers, and a delete action with confirmation that explains what happens to the column's cards. Refetch board data after each mutation and when the tab regains focus. No drag and drop yet. Tests: renders columns and cards from mocked data; column rename.

## 24. Add drag-and-drop for cards and columns
Goal: Cards can be dragged between and within columns, and columns can be reordered.
Description: Integrate a drag-and-drop library (e.g. `@dnd-kit`) into the board page from task 23. Dropping a card calls the card `PATCH` with the new column and position; dragging a column header calls the column `PATCH` with a new position. Apply the change optimistically and roll back on error. Keep animations minimal. Add a test for the position-calculation helper.

## 25. Build the card detail modal with checklist and comments (absorbs #26)
Goal: Clicking a card opens a modal where all fields, the checklist and comments can be edited.
Description: Add a modal opened from a board card that edits title, description, column, priority, due date, assignee (from board members), labels (multi-select with the ability to create a new label) and shows the parent card if any; save via the card `PATCH` endpoint and include a delete button. Add a checklist section (add, edit, toggle, reorder, remove items with a completed count) and a comments section (list with author and time, add comment, edit/delete own comments) using the `/cards/{id}/checklist` and `/cards/{id}/comments` endpoints. Ensure keyboard support (Escape closes, focus trapped). Tests: open the modal with mocked data and save a field change; toggle a checklist item; post a comment.

## 33. Build the AI card actions and natural-language task creation UI (absorbs #34)
Goal: From the card modal, users can run the five AI actions and approve results before they apply; from the board, users can create a card from a sentence.
Description: Add an "AI" menu in the card modal with Break down, Improve, Prioritize, Estimate effort and Summarize. Each shows a preview panel with the AI text and, where applicable, the proposed change (new description, priority, estimate, or an editable list of child tasks) with Approve/Discard buttons. Approve calls the relevant apply/`PATCH` endpoint; Discard changes nothing. Add a "New task from text" input on the board that calls `POST /ai/create-task`, shows the proposed card in the card modal for editing, and creates it via the normal card `POST` on approval. No assistant/chat panel. Tests: Approve triggers the write call and Discard does not; the preview-then-create flow with a mocked client.
