# Mini Kanban Board — Task Backlog

Derived from `_docs/plan.md`. Each task is sized for one working session and written so it can be picked up without reading the others. Shared context every task assumes:

- Repo layout: `backend/` (FastAPI, Python, SQLAlchemy, SQLite, pytest) and `frontend/` (Next.js, TypeScript, Tailwind CSS).
- Backend code lives under `backend/app/` with `models/`, `schemas/`, `routers/`, `services/`, `websocket/`; tests under `backend/tests/`.
- Auth is JWT (email/password). Board roles are `owner` and `member`. Boards are private to owner + members.
- AI provider is Google Gemini. AI endpoints only return suggestions; the user must approve before anything is written.
- Deployment is local only. No Alembic; tables are created directly from SQLAlchemy models.

Tasks are ordered so earlier ones are natural prerequisites, but each description states what it expects to already exist.

---

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

## 5. Implement board CRUD with owner/member permissions
Goal: Authenticated users can create, list, view, rename and delete boards they belong to.
Description: Add `GET/POST /boards`, `GET/PATCH/DELETE /boards/{board_id}` (assumes models and auth from tasks 3–4). Creating a board also creates a BoardMember row with role `owner` and the three default columns "To Do", "In Progress", "Done". Only members can view/rename; only the owner can delete. Write permission tests covering: non-member gets 404/403, member cannot delete, owner can delete, and listing returns only boards the user belongs to.

## 6. Implement column management
Goal: Board members can create, rename, reorder and delete columns.
Description: Add `POST /boards/{board_id}/columns`, `PATCH /columns/{column_id}` (name and/or position) and `DELETE /columns/{column_id}` (assumes boards and auth exist). Deleting a column should either be refused when it still holds cards or move them to the first remaining column — pick one and document it in the router docstring. Include a `position` reorder strategy that keeps positions contiguous, and test create/rename/reorder/delete plus the rule that non-members are rejected.

## 7. Implement card CRUD and card movement
Goal: Board members can create, read, update, move and delete cards.
Description: Add `POST/GET /boards/{board_id}/cards`, `GET/PATCH/DELETE /cards/{card_id}` (assumes boards and columns exist). Cards carry title, description, column, priority, due date, assignee, optional parent card, and a manual `position` within their column. `PATCH` must support moving a card to another column and reordering within a column while keeping positions consistent. Test create, update, move between columns, reorder, delete, and that a card cannot reference a parent on a different board.

## 8. Implement labels and card labels
Goal: Boards have labels, and cards can carry any number of them.
Description: Add endpoints to create, list, rename and delete labels per board (`/boards/{board_id}/labels`), and to attach/detach labels on a card (e.g. via the card `PATCH` accepting `label_ids`, or dedicated `/cards/{card_id}/labels/{label_id}` routes). Deleting a label removes it from all cards. Tests should cover creation, attaching two labels to a card, detaching one, and label deletion cascading.

## 9. Implement checklists on cards
Goal: Each card can have a flat list of checklist items that can be added, edited, toggled, reordered and removed.
Description: Add endpoints under `/cards/{card_id}/checklist` for creating items, and `PATCH/DELETE /checklist/{item_id}` for editing content, toggling `completed`, and reordering by `position`. No nesting. The card detail response should include its checklist items in order. Test add, edit, toggle, reorder and delete, plus rejection for users who are not members of the card's board.

## 10. Implement comments on cards
Goal: Board members can post, read, edit and delete plain-text comments on cards.
Description: Add `POST/GET /cards/{card_id}/comments` and `PATCH/DELETE /comments/{comment_id}`. Each comment records author, content, created and updated timestamps; responses should include the author's display name. Only the author may edit or delete their own comment. Test posting, listing in chronological order, editing by the author, and rejection when a different member tries to edit.

## 11. Implement board invitations and membership management
Goal: Owners can invite users via a permanent invite link and manage members.
Description: Add an endpoint for the owner to fetch/generate the board's permanent invite token, an endpoint an authenticated user calls with that token to join as `member`, and endpoints to list and remove members (owner only; the owner cannot be removed). Also support inviting by email address so an existing user is added directly. Tests: joining via a valid token, invalid token rejected, non-owner cannot remove members, joining twice is idempotent.

## 12. Implement the activity log
Goal: Major card events are recorded and can be listed per board.
Description: Add an `Activity` recording helper in `backend/app/services/` and call it from the card create, edit, move and delete paths (assumes card endpoints exist). Store a human-readable action string such as `moved "Implement authentication" from In Progress to Done`. Add `GET /boards/{board_id}/activity` returning the most recent entries newest-first, including the actor's display name. Test that each of the four card operations produces exactly one entry with the expected text.

## 13. Implement the dashboard statistics endpoint
Goal: A single endpoint returns the four simple board metrics.
Description: Add `GET /boards/{board_id}/dashboard` returning total card count, counts grouped by column, overdue count (`due_date < now` and column is not "Done"), and progress percentage (`cards in Done / total * 100`, 0 when there are no cards). Decide how "Done" is identified (by column name match) and document it. Test each metric with a small fixture board, including the zero-card case.

## 14. Implement card search and filtering
Goal: The card list endpoint supports search and the five filters.
Description: Extend `GET /boards/{board_id}/cards` with query parameters: `q` (case-insensitive match on title or description), `column_id`, `priority`, `label_id`, `assignee_id`, and a due-date filter (e.g. `due_before` / `due_after` / `overdue=true`). Filters combine with AND. No saved filters. Test search on title vs description, each filter individually, and a combination.

## 15. Implement real-time board updates over WebSockets
Goal: Connected board members receive events when the board changes.
Description: Add `WS /ws/boards/{board_id}` that authenticates the JWT (query param or first message), rejects non-members, and registers the socket in a per-board connection manager in `backend/app/websocket/`. Broadcast JSON events for card created/edited/moved/deleted, column changes, checklist changes, comments and membership changes by calling the manager from the existing routers. Test with FastAPI's WebSocket test client: two clients connect, one triggers a card update via HTTP, the other receives the event.

## 16. Integrate Gemini and implement the single-card AI actions
Goal: The Improve, Prioritize, Estimate effort and Summarize actions return previews without changing the card.
Description: Add a Gemini client in `backend/app/services/ai.py` behind a small interface so tests can inject a fake. Implement `POST /ai/card/{card_id}/improve|prioritize|estimate|summarize` using only the current card's fields as context; each returns natural-language text plus, where relevant, structured proposed values (priority; size Small/Medium/Large and a time estimate). Nothing is written to the database. Test each endpoint with the fake client and verify the card is unchanged afterwards.

## 17. Implement AI task breakdown with approval
Goal: A card can be broken into proposed child cards that are only created after the user approves.
Description: Add `POST /ai/card/{card_id}/breakdown` returning a list of proposed child tasks (title, description) generated from the card (assumes the Gemini client from task 16). Add an approval endpoint (e.g. `POST /ai/card/{card_id}/breakdown/apply`) that accepts the user-edited list and creates child cards with `parent_card_id` set, in the same column as the parent. Test that the preview creates nothing, and that apply creates the given children with the correct parent and board.

## 18. Implement natural-language task creation with approval
Goal: A user can type a sentence and get a proposed card to review before it is created.
Description: Add `POST /ai/create-task` taking a board id and free text, returning a proposed card (title, description, priority, due date if mentioned) without saving it. Creation happens through the normal card `POST` once the user approves in the UI, so no extra write endpoint is required — document that contract in the router. Test with a fake Gemini response that the preview is returned and no card exists afterwards.

## 19. Implement the board-level AI project assistant
Goal: Users can ask questions about the current board and get a natural-language answer.
Description: Add `POST /ai/project-assistant` taking a board id and question. Build the prompt context from the board name, columns, cards, priorities, due dates, assignees and labels only — explicitly exclude comments, activity history and other boards. Return the answer as text. Test that the context builder includes cards and excludes comments, and that non-members are rejected.

## 20. Create the seed data script
Goal: One command populates a realistic demo board for local use and demos.
Description: Add `backend/scripts/seed.py` that creates two or three demo users and an "Insurance Policy Automation" board with columns Backlog, To Do, In Progress, Review, Done. Populate it with several cards spanning priorities, due dates (some overdue), labels, assignees, checklists, comments, at least one parent/child pair and activity entries. The script must be idempotent (re-running does not duplicate). Add a test that runs the seed against an in-memory database and asserts on counts.

## 21. Build the frontend API client and auth pages
Goal: Users can sign up, log in and log out from the browser.
Description: Add a typed API client in `frontend/` that reads the backend URL from an environment variable, attaches the JWT from storage, and exposes `signup`, `login`, `me`. Build Login and Sign up pages in the dark minimal style, an auth context/provider, and a route guard that redirects unauthenticated users. Add a component test for the login form (validation and successful submit with a mocked client).

## 22. Build the board list page
Goal: Logged-in users see their boards and can create, rename and delete them.
Description: Add a `/boards` page listing the user's boards from `GET /boards`, with a create-board form, inline rename, and a delete action shown only to the owner with a confirmation. Clicking a board navigates to `/boards/[id]`. Keep the layout compact and low-noise. Add a test that renders the list from mocked data and exercises create.

## 23. Build the board page with columns and cards (static rendering)
Goal: The board screen shows columns and cards and supports creating a card.
Description: Add `/boards/[id]` that loads the board, its columns and cards and renders them as horizontal columns of compact cards showing title, priority, due date, labels and assignee. Include an "add card" input at the bottom of each column and a status dropdown on each card for moving it between columns. No drag and drop yet. Add a test that renders columns and cards from mocked data.

## 24. Add drag-and-drop for cards and columns
Goal: Cards can be dragged between and within columns, and columns can be reordered.
Description: Integrate a drag-and-drop library (e.g. `@dnd-kit`) into the board page from task 23. Dropping a card calls the card `PATCH` with the new column and position; dragging a column header calls the column `PATCH` with a new position. Apply the change optimistically and roll back on error. Keep animations minimal. Add a test for the position-calculation helper.

## 25. Build the card detail modal (core fields)
Goal: Clicking a card opens a modal where all standard fields can be edited.
Description: Add a modal opened from a board card that edits title, description, column, priority, due date, assignee (from board members), labels (multi-select with the ability to create a new label) and shows the parent card if any. Save via the card `PATCH` endpoint and include a delete button. Ensure keyboard support (Escape closes, focus trapped). Add a component test that opens the modal with mocked data and saves a field change.

## 26. Add checklist and comments to the card modal
Goal: The card modal supports checklists and comments.
Description: Extend the card modal with a checklist section (add, edit, toggle, reorder, remove items with a completed count) and a comments section (list with author and time, add comment, edit/delete own comments). Use the `/cards/{id}/checklist` and `/cards/{id}/comments` endpoints. Add tests for toggling a checklist item and posting a comment.

## 27. Build column management UI
Goal: Members can add, rename and delete columns from the board page.
Description: Add an "add column" control at the end of the board, inline rename on column headers, and a delete action with confirmation that explains what happens to the column's cards. Calls the column endpoints. Add a test covering rename.

## 28. Build search and filter controls on the board
Goal: Users can search cards and filter by status, priority, label, assignee and due date.
Description: Add a compact toolbar above the board with a search input and filter dropdowns for column, priority, label, assignee and a due-date option (e.g. overdue / due this week). Pass the values as query parameters to `GET /boards/{id}/cards` and re-render the board; show an active-filter count and a clear button. Add a test that the query string is built correctly from selected filters.

## 29. Add the WebSocket listener for live updates
Goal: Changes made by other members appear on the board without refreshing.
Description: Add a client hook that connects to `WS /ws/boards/{id}` with the JWT, reconnects on drop, and applies incoming card/column/checklist/comment/membership events to the board state (and the open card modal if relevant). Ignore events that originate from the current client's own optimistic updates when they would cause flicker. Add a unit test for the event-to-state reducer.

## 30. Build the invitation and member management flow
Goal: Owners can share an invite link and manage members; invitees can join.
Description: Add a board "Members" panel that lists members with roles, lets the owner copy the permanent invite link, invite by email, and remove members. Add an `/invite/[token]` page that, for a logged-in user, calls the join endpoint and redirects to the board (redirecting to login first if needed). Add a test for the invite page's join-then-redirect behaviour.

## 31. Build the dashboard page
Goal: A simple per-board dashboard shows four metrics.
Description: Add `/boards/[id]/dashboard` that calls `GET /boards/{id}/dashboard` and shows total tasks, tasks by status, overdue tasks and a progress percentage with a simple bar. No charts, trends or timelines. Link to it from the board header. Add a test that renders the metrics from mocked data, including the zero-task state.

## 32. Build the activity log view
Goal: Members can see recent board activity.
Description: Add a collapsible activity panel or side sheet on the board page that lists entries from `GET /boards/{id}/activity`, newest first, formatted like `Freya moved "Implement authentication" from In Progress to Done`. Refresh when the WebSocket delivers a relevant event if the listener exists; otherwise refetch on open. Add a rendering test.

## 33. Build the AI card actions with preview and approve
Goal: From the card modal, users can run the five AI actions and approve results before they apply.
Description: Add an "AI" menu in the card modal with Break down, Improve, Prioritize, Estimate effort and Summarize. Each shows a preview panel with the AI text and, where applicable, the proposed change (new description, priority, estimate, or an editable list of child tasks) with Approve/Discard buttons. Approve calls the relevant apply/`PATCH` endpoint; Discard changes nothing. Add a test that Approve triggers the write call and Discard does not.

## 34. Build natural-language task creation and the project assistant UI
Goal: Users can create a card from a sentence and chat with the board assistant.
Description: Add a "New task from text" input on the board that calls `POST /ai/create-task`, shows the proposed card in the card modal for editing, and creates it via the normal card `POST` on approval. Add a small assistant panel that sends questions to `POST /ai/project-assistant` and shows the answer thread for the current session only (no persistence). Add tests for the preview-then-create flow with a mocked client.

## 35. Build the profile/settings page
Goal: Users can view and update their display name and log out.
Description: Add a `/settings` page showing email and an editable display name, backed by `GET /auth/me` and a `PATCH /auth/me` endpoint (add the backend endpoint if it does not exist: display name only). Include a logout button that clears the token and redirects to login. Add a test for saving the display name.

## 36. Write the top-level README and local run instructions
Goal: A newcomer can run the whole app locally by following one document.
Description: Write the root `README.md` covering prerequisites, environment variables (backend secret, database path, Gemini API key, frontend API URL), how to start the backend and frontend, how to run the seed script, and how to run both test suites. Include a short architecture overview and a screenshot placeholder list. Verify the instructions by following them from a clean checkout.
