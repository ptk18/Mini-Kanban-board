# Mini Kanban

A small Kanban board for a team: boards with columns and cards, labels,
checklists, comments, invite links, a per-board dashboard, and Gemini-backed
card actions that only ever *propose* changes. Runs locally: a FastAPI +
SQLite backend and a Next.js frontend.

The product plan is in [`_docs/plan.md`](_docs/plan.md) and the backlog in
[`_docs/tasks.md`](_docs/tasks.md); work is tracked as GitHub issues, one per
task. Each app has its own README with the full command reference:
[`backend/README.md`](backend/README.md), [`frontend/README.md`](frontend/README.md).

## Prerequisites

| Tool | Version | Used by |
|---|---|---|
| [`uv`](https://docs.astral.sh/uv/) | 0.11+ | backend (installs Python 3.14 itself if needed) |
| Python | 3.14 (`backend/.python-version`) | backend |
| Node.js | 20.9+ | frontend |
| npm | ships with Node | frontend |
| `curl` | any | the smoke checks below |

## Environment variables

All backend variables are read from the shell that runs the server; there is
no `.env` file handling. The test suites set their own values.

| Variable | App | Required | Meaning |
|---|---|---|---|
| `JWT_SECRET` | backend | **yes** for the server | HS256 secret for access tokens, at least 32 characters. The server refuses to start without it. Changing it logs everyone out. |
| `DATABASE_URL` | backend | no | SQLAlchemy URL; default `sqlite:///./mini_kanban.db` (a file in `backend/`). `sqlite://` is in-memory. |
| `GEMINI_API_KEY` | backend | only for `/ai/...` | Google Gemini API key. Without it the AI routes answer `503`; everything else works. |
| `GEMINI_MODEL` | backend | no | Gemini model, default `gemini-2.5-flash`. |
| `CORS_ORIGINS` | backend | no | Browser origins allowed to call the API — **not implemented yet** (issue #37). Until then the frontend must be served from the same origin or use a dev proxy. |
| `NEXT_PUBLIC_API_URL` | frontend | — | Backend base URL for the browser, e.g. `http://127.0.0.1:8000` — **read by the API client from issue #21, not yet in the code.** |

Generate a secret:

```sh
uv run --directory backend python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Run it

Two terminals.

**Backend** (from `backend/`):

```sh
cd backend
uv sync
export JWT_SECRET=$(uv run python -c "import secrets; print(secrets.token_urlsafe(32))")
uv run uvicorn app.main:app --reload
```

Serves `http://127.0.0.1:8000`; tables are created on first start (no
migrations — after a model change, delete `mini_kanban.db` and restart).
`http://127.0.0.1:8000/docs` is the interactive API. Smoke check:

```sh
curl -s http://127.0.0.1:8000/health
# {"status":"ok"}
```

**Frontend** (from `frontend/`):

```sh
cd frontend
npm ci
npm run dev
```

Serves `http://localhost:3000` (a dark placeholder page; the auth and board
screens are issues #21–#25).

## Seed a demo board

With the backend installed (the server does not need to be running; the
script writes to the same `DATABASE_URL`):

```sh
cd backend
uv run python scripts/seed.py
```

Creates three users and an **Insurance Policy Automation** board with the
columns Backlog / To Do / In Progress / Review / Done, 14 cards across every
priority (three of them overdue), five labels, checklists, comments and a
parent/child pair. Running it again is a no-op ("Nothing to do").

Seed accounts — the password is `insurance-demo` for all three:

| Email | Role on the board |
|---|---|
| `ada@example.com` | owner |
| `grace@example.com` | member |
| `linus@example.com` | member |

```sh
TOKEN=$(curl -s http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ada@example.com", "password": "insurance-demo"}' \
  | uv run python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
curl -s http://127.0.0.1:8000/boards -H "Authorization: Bearer $TOKEN"
```

## Run the tests

```sh
cd backend && uv run pytest          # FastAPI TestClient + in-memory SQLite, no server needed
cd frontend && npm test              # Vitest + React Testing Library, single run
```

Conventions for writing tests are in
[`_docs/testing-guidelines.md`](_docs/testing-guidelines.md).

## Architecture

```text
frontend/   Next.js 16 (App Router), TypeScript, Tailwind CSS 4, Vitest
backend/    FastAPI, SQLAlchemy 2, SQLite, PyJWT + bcrypt, pytest
_docs/      plan, backlog, design system, testing guidelines, team roles
```

Backend layout (`backend/app/`):

- `main.py` — app factory, startup check for `JWT_SECRET`, `create_all()`, router registration
- `database.py` — engine, `Base`, `get_db`, the naive-UTC `utcnow()` helper
- `models/` — one module per table: `User`, `Board`, `BoardMember`, `Column`, `Card`, `Label`/`CardLabel`, `ChecklistItem`, `Comment` (`Activity` exists but is unused in the MVP)
- `schemas/` — Pydantic request/response models; every `*Out` timestamp is serialised with an explicit UTC offset
- `routers/` — `auth`, `boards`, `columns`, `cards`, `labels`, `checklist`, `comments`, `members`, `dashboard`, `ai`
- `services/` — `auth` (bcrypt + JWT, `get_current_user`), `access` (board-membership dependencies: non-member → `404`, non-owner → `403`), `ordering` (contiguous positions), `cards`, `columns`, `checklist`, `ai` (Gemini client behind a fake-able interface)
- `scripts/seed.py` — the demo data

Key rules the API follows:

- Auth is a bearer JWT (`POST /auth/signup` or `/auth/login`); every failure is `401` with `WWW-Authenticate: Bearer`.
- A board is private to its owner and members. Non-members get `404` (ids are not enumerable); owner-only actions give members `403`.
- Positions (columns in a board, cards in a column, checklist items on a card) are 0-based and kept contiguous by the server.
- AI routes return previews. The only AI route that writes is `POST /ai/card/{id}/breakdown/apply`, which takes the list the user approved. Everything else is applied through the normal `PATCH`/`POST` routes.
- No migrations: tables come straight from the models.

The visual direction (dark developer tool, minimal) is in
[`_docs/design-system.md`](_docs/design-system.md).

## Screenshots

_Placeholders until the frontend screens land (issues #21–#25):_

- Login / Sign up
- Board list
- Board with columns and cards
- Card modal (fields, labels, checklist, comments, AI actions)
- Dashboard
- Invite flow
