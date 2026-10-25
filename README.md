# Mini Kanban

[![CI](https://github.com/ptk18/Mini-Kanban-board/actions/workflows/ci.yml/badge.svg)](https://github.com/ptk18/Mini-Kanban-board/actions/workflows/ci.yml)

A small Kanban board for a team: boards with columns and cards, labels,
checklists, comments, invite links, a per-board dashboard, and Gemini-backed
card actions that only ever *propose* changes. Runs locally: a FastAPI +
backend (SQLite for a quick start, Postgres in Docker and production) and a
Next.js frontend.

The product plan is in [`_docs/plan.md`](_docs/plan.md) and the backlog in
[`_docs/tasks.md`](_docs/tasks.md); work is tracked as GitHub issues, one per
task. Each app has its own README with the full command reference:
[`backend/README.md`](backend/README.md), [`frontend/README.md`](frontend/README.md).

## Prerequisites

| Tool | Version | Used by |
|---|---|---|
| [Docker](https://docs.docker.com/get-docker/) with Compose v2 | 24+ | the one-command stack (`docker compose up`); nothing else is needed for that path |
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
| `DATABASE_URL` | backend | no | SQLAlchemy URL; default `sqlite:///./mini_kanban.db` (a file in `backend/`). `sqlite://` is in-memory. `postgresql+psycopg://user:pass@host/db` selects Postgres, migrated by Alembic on startup. |
| `GEMINI_API_KEY` | backend | only for `/ai/...` | Google Gemini API key. Without it the AI routes answer `503`; everything else works. |
| `GEMINI_MODEL` | backend | no | Gemini model, default `gemini-2.5-flash`. |
| `CORS_ORIGINS` | backend | no | Comma-separated browser origins allowed to call the API. Default `http://localhost:3000` (the Next.js dev server). |
| `NEXT_PUBLIC_API_URL` | frontend | no | Backend base URL as seen from the browser. Default `http://127.0.0.1:8000`; set it in `frontend/.env.local` (see `frontend/.env.example`). |

Generate a secret:

```sh
uv run --directory backend python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Run it

### One command (Docker Compose)

Starts Postgres, the backend (migrations applied on start) and the frontend:

```sh
docker compose up --build        # or: make up
```

Then open `http://localhost:3000` and sign up, or load the demo board first
(see [Seed a demo board](#seed-a-demo-board)). The API is at
`http://localhost:8000` (`/docs` is interactive). Every variable has a
laptop-only default in `docker-compose.yml`; to change one, `cp .env.example
.env` and edit it. The frontend bakes `NEXT_PUBLIC_API_URL` into its bundle,
so changing that one needs `docker compose up --build`.

Data lives in the `pgdata` volume and survives `docker compose down`;
`docker compose down -v` wipes it. `make help` lists the shortcuts
(`up`, `down`, `logs`, `ps`, `seed`, `test`).

### Two terminals (development, SQLite)

**Backend** (from `backend/`):

```sh
cd backend
uv sync
export JWT_SECRET=$(uv run python -c "import secrets; print(secrets.token_urlsafe(32))")
uv run uvicorn app.main:app --reload
```

Serves `http://127.0.0.1:8000` on a SQLite file; tables are created on first
start (after a model change, delete `mini_kanban.db` and restart, or point
`DATABASE_URL` at Postgres to use the Alembic migrations — see
[`backend/README.md`](backend/README.md#database)).
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

Serves `http://localhost:3000`: sign up or log in, manage boards at `/boards`,
work on a board at `/boards/[id]` (columns, cards, filters, members, invite
links, card modal with AI actions, new task from text) and see its dashboard at `/boards/[id]/dashboard`.

## Seed a demo board

Against the Compose stack:

```sh
docker compose exec backend python scripts/seed.py     # or: make seed
```

Against a local backend (the server does not need to be running; the script
writes to the same `DATABASE_URL`):

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
make test                            # every layer below, one command, non-zero exit on any failure
make test-unit                       # the two fast suites, no Docker
cd backend && uv run pytest          # backend unit: FastAPI TestClient + in-memory SQLite
cd frontend && npm test              # frontend unit: Vitest + React Testing Library
make test-integration                # backend against a real Postgres (Compose db): migrations, seed, the main journey
make test-e2e                        # Playwright in Chromium against the whole Compose stack
```

The browser tests need `cd frontend && npx playwright install chromium` once.
What each layer proves and how they are kept apart is in
[`docs/testing.md`](docs/testing.md); conventions for writing tests are in
[`_docs/testing-guidelines.md`](_docs/testing-guidelines.md).

## Architecture

```text
frontend/           Next.js 16 (App Router), TypeScript, Tailwind CSS 4, Vitest; Dockerfile (standalone output)
backend/            FastAPI, SQLAlchemy 2, SQLite or Postgres (Alembic), PyJWT + bcrypt, pytest; Dockerfile
docker-compose.yml  db (Postgres 17) + backend + frontend, one command
Makefile            up / down / logs / seed / test / test-integration / test-e2e shortcuts
docs/               testing (more arrive with deployment, observability, on-call)
_docs/              plan, backlog, design system, testing guidelines, team roles
```

Backend layout (`backend/app/`):

- `main.py` — app factory, startup check for `JWT_SECRET`, `prepare_database()`, router registration
- `database.py` — engine, `Base`, `get_db`, the naive-UTC `utcnow()` helper, `prepare_database()` (`create_all` on SQLite, Alembic `upgrade head` on Postgres)
- `alembic/` — migrations; `alembic/env.py` reads `DATABASE_URL`
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
- Schema: SQLite gets `create_all` straight from the models; Postgres gets Alembic migrations (`backend/alembic/`), run automatically on startup.

The visual direction (dark developer tool, minimal) is in
[`_docs/design-system.md`](_docs/design-system.md).

## Screenshots

_Placeholders:_

- Login / Sign up (`/login`, `/signup`)
- Board list (`/boards`)
- Board with columns, cards, toolbar and members panel (`/boards/[id]`)
- Card modal (fields, labels, checklist, comments, AI actions)
- Dashboard (`/boards/[id]/dashboard`)
- Invite flow (`/invite/[token]`)
