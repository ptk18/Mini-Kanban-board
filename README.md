# Mini Kanban

[![CI](https://github.com/ptk18/Mini-Kanban-board/actions/workflows/ci.yml/badge.svg)](https://github.com/ptk18/Mini-Kanban-board/actions/workflows/ci.yml)
[![Deploy](https://github.com/ptk18/Mini-Kanban-board/actions/workflows/deploy.yml/badge.svg)](https://github.com/ptk18/Mini-Kanban-board/actions/workflows/deploy.yml)

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

## Deployment

The repository is deploy-ready for [Render](https://render.com): the
Blueprint is [`render.yaml`](render.yaml), continuous delivery is
[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) (dev deploys
automatically after green CI, production is a manual, approval-gated run, and
rollback is one click or one `ref=`). Setup steps for the owner are in
[`docs/deployment.md`](docs/deployment.md); the release and rollback flow in
[`docs/release-process.md`](docs/release-process.md).

**Public URL:** _to be added once the Render account is created and the first
deploy has run._ Until then the deploy workflow exits green with a "skipped"
notice.

## Observability

```sh
make observe        # app + OpenTelemetry Collector, Prometheus, Loki, Tempo, Grafana
```

Grafana at `http://localhost:3001/d/mini-kanban` shows request rate, latency
percentiles, 5xx ratio, the `/health` probe, cards moved per minute, the API
logs and the slowest traces. Every request produces a span, a JSON log line
and metric points that share one `trace_id`; a log line links to its trace
and a span links back to its logs. Nothing user-supplied (e-mails, tokens,
titles) is in any signal. Details and the metric reference:
[`docs/observability.md`](docs/observability.md).

Two alerts watch user impact, not machines: **KanbanApiErrors** (over 5 %
of board/card requests failing for 30 s) and **KanbanApiDown** (`/health`
unanswered for a minute). `make demo-alert` breaks card moves on purpose
and shows the first one go pending → firing in about a minute, then clears
the fault. Rules, thresholds and the demo: [`docs/alerting.md`](docs/alerting.md).

When an alert fires, Alertmanager calls a webhook that starts an **on-call
responder**: headless Claude Code, given a bounded read-only evidence
packet and an isolated git worktree, no credentials, a tool allowlist and a
dollar cap. It answers in a fixed JSON schema; a policy file decides which
proposed actions run automatically (clear the demo fault, or commit a
tested fix on an un-pushed branch) and which go to a human. Recovery is
verified against Prometheus and the smoke test, not taken on the model's
word. `make demo-oncall` runs the whole incident; a recorded run is in
[`docs/oncall-demo.md`](docs/oncall-demo.md), the design in
[`docs/oncall.md`](docs/oncall.md).

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
render.yaml         Render Blueprint: dev + prod services and databases
.github/workflows/  ci.yml (every PR/push) and deploy.yml (dev automatic, prod manual)
scripts/smoke.sh    post-deploy check: /health reports the expected sha, /login renders
observability/      compose overlay + Collector, Prometheus, Alertmanager, Loki, Tempo, Grafana configs, dashboards/mini-kanban.json
oncall/             webhook receiver, responder, evidence collector, autonomy policy, answer schema, recovery check
Makefile            up / down / logs / seed / observe / demo-alert / oncall / demo-oncall / test / test-integration / test-e2e
docs/               testing, deployment, release process, observability, alerting, on-call (+ the recorded demo)
_docs/              plan, backlog, design system, testing guidelines, team roles
```

Backend layout (`backend/app/`):

- `main.py` — app factory, startup check for `JWT_SECRET`, `prepare_database()`, telemetry wiring, router registration
- `telemetry.py` — structlog JSON logs with trace ids, OpenTelemetry traces/metrics, request-logging middleware, redaction
- `version.py` — the deployed commit for `/health` and `service.version`
- `database.py` — engine, `Base`, `get_db`, the naive-UTC `utcnow()` helper, `prepare_database()` (`create_all` on SQLite, Alembic `upgrade head` on Postgres)
- `alembic/` — migrations; `alembic/env.py` reads `DATABASE_URL`
- `models/` — one module per table: `User`, `Board`, `BoardMember`, `Column`, `Card`, `Label`/`CardLabel`, `ChecklistItem`, `Comment` (`Activity` exists but is unused in the MVP)
- `schemas/` — Pydantic request/response models; every `*Out` timestamp is serialised with an explicit UTC offset
- `routers/` — `auth`, `boards`, `columns`, `cards`, `labels`, `checklist`, `comments`, `members`, `dashboard`, `ai` (+ `debug`, only when `FAULT_INJECTION` is set)
- `fault.py` — the demo fault switch behind `/debug/fault`; a no-op unless switched on
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

| | |
|---|---|
| ![Board](docs/images/board.png) **Board** — columns, cards with priority, due date, labels and assignee, filters, new task from text | ![Card modal](docs/images/card-modal.png) **Card** — fields, labels, AI actions, checklist, comments |
| ![Dashboard](docs/images/dashboard.png) **Dashboard** — totals, by column, overdue, progress | ![Grafana](docs/images/grafana-dashboard.png) **Operations** — request rate, latency, 5xx ratio, card moves, logs with trace links |

Also [login](docs/images/login.png) and the [board list](docs/images/boards.png).
Regenerate with `cd frontend && node e2e/screenshots.mjs ../docs/images`
against a seeded stack, and the Grafana one with `observability/screenshot.mjs`.

## How this was built with AI tools

The whole project was built with [Claude Code](https://claude.com/claude-code)
as the engineer, following the AI Dev Tools Zoomcamp workflow:

1. **Specify first.** The product spec ([`_docs/plan.md`](_docs/plan.md)) and
   a backlog ([`_docs/tasks.md`](_docs/tasks.md),
   [`_docs/tasks-production.md`](_docs/tasks-production.md)) were written
   before any code, then turned into GitHub issues with acceptance criteria
   ([template](_docs/task-template.md)).
2. **One issue at a time, three roles.** [`_docs/process.md`](_docs/process.md)
   defines a PM who grooms, an engineer who implements and a QA who checks
   acceptance criteria ([`_docs/team/`](_docs/team/)). Every issue is
   closed with a comment listing what shipped and the exact verification
   that was run, so issue → commit → evidence is traceable, e.g.
   [#24 drag and drop](https://github.com/ptk18/Mini-Kanban-board/issues/24),
   [#39 Postgres + Alembic](https://github.com/ptk18/Mini-Kanban-board/issues/39),
   [#44 observability](https://github.com/ptk18/Mini-Kanban-board/issues/44),
   [#46 on-call agent](https://github.com/ptk18/Mini-Kanban-board/issues/46).
3. **Durable context for agents.** [`AGENTS.md`](AGENTS.md) carries the
   commands, the rules and an index of every document; the frontend has its
   own note about the Next.js version. Conventions live in docs, not in
   chat history ([testing guidelines](_docs/testing-guidelines.md),
   [design system](_docs/design-system.md)).
4. **Verify by running, not by reading.** Each closing comment quotes test
   counts, curl output, Prometheus/Loki/Tempo queries, CI run links or the
   recorded alert timeline. Where something could not be verified (the Render
   account, branch protection) the comment says so and names the owner action.
5. **An agent in production too.** The on-call responder
   ([`oncall/`](oncall/)) is headless Claude Code inside a policy: bounded
   evidence, a worktree, a tool allowlist, a JSON schema, and recovery
   verified by observation. [`docs/oncall-demo.md`](docs/oncall-demo.md) is a
   recorded run.

Things the model got wrong and the process caught: a `setup-uv` action
version that does not exist as a floating tag (CI), a Tempo config key that
Tempo 3 rejects (container exit), an alert rule that could never fire
because of Prometheus lookback (recorded stop/start test), and a JSON schema
header that silently disables Claude Code's structured output (the
responder's escalation path). Each is documented where it was found.

## Rubric map

| # | Criterion | Where to look |
|---|---|---|
| 1 | Problem description | this README, top; [`_docs/plan.md`](_docs/plan.md) §1–3 |
| 2 | Product specification + public tracker | [`_docs/plan.md`](_docs/plan.md), [`_docs/tasks.md`](_docs/tasks.md), [`_docs/tasks-production.md`](_docs/tasks-production.md); [issues #1–#47](https://github.com/ptk18/Mini-Kanban-board/issues?q=is%3Aissue) with acceptance criteria and closing evidence |
| 3 | Agent team specification | [`_docs/process.md`](_docs/process.md), [`_docs/team/`](_docs/team/) |
| 4 | Context management | [`AGENTS.md`](AGENTS.md) (commands, rules, index of all docs), [`frontend/AGENTS.md`](frontend/AGENTS.md) |
| 5 | Application | Next.js + FastAPI + Postgres, `docker compose up --build`, [Run it](#run-it) |
| 6 | Testing | unit + integration + e2e, `make test`, [`docs/testing.md`](docs/testing.md) |
| 7 | Containerization | [`docker-compose.yml`](docker-compose.yml), `backend/Dockerfile`, `frontend/Dockerfile` |
| 8 | Deployment | [`render.yaml`](render.yaml), [`docs/deployment.md`](docs/deployment.md) — steps documented; public URL pending the owner's Render account |
| 9 | CI/CD | [`ci.yml`](.github/workflows/ci.yml) on every PR/push; [`deploy.yml`](.github/workflows/deploy.yml): dev automatic after green CI, production manual with approval; [`docs/release-process.md`](docs/release-process.md) |
| 10 | Observability | [`docs/observability.md`](docs/observability.md): traces, metrics and structured logs sharing a `trace_id`, no customer data, Grafana over Prometheus/Loki/Tempo |
| 11 | Alerting on user impact | [`observability/alerts.yaml`](observability/alerts.yaml), [`docs/alerting.md`](docs/alerting.md), `make demo-alert` |
| 12 | On-call agent | [`oncall/`](oncall/), [`docs/oncall.md`](docs/oncall.md), [`docs/oncall-demo.md`](docs/oncall-demo.md), `make demo-oncall` |
