# Mini Kanban — backend

FastAPI backend for the Mini Kanban board. It serves the smoke-test endpoint
`GET /health`, email/password authentication with JWT bearer tokens
(`POST /auth/signup`, `POST /auth/login`, `GET /auth/me`), and defines the
database layer (SQLite or Postgres; SQLAlchemy 2.x models for users, boards, columns, cards,
labels, checklist items, comments and activity). There is no board or card
business logic yet.

All commands below are run from `backend/`.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (0.11 or newer)
- Python 3.14 (`uv` picks it up from `.python-version`; `uv python install 3.14` if it is missing)

## Install

```sh
uv sync
```

Creates `.venv/` and installs the runtime and `dev` dependency groups from `uv.lock`.

## Run the server

The server needs the `JWT_SECRET` environment variable (see
[Configuration](#configuration)). Generate one and start the server:

```sh
export JWT_SECRET=$(uv run python -c "import secrets; print(secrets.token_urlsafe(32))")
uv run uvicorn app.main:app --reload
```

Uvicorn prints the listening address (`http://127.0.0.1:8000` by default).

Without `JWT_SECRET` the server refuses to start: uvicorn logs
`Application startup failed` with a `RuntimeError: JWT_SECRET must be set ...`
traceback and exits non-zero, and nothing listens on the port.

`/health` is the smoke-test endpoint:

```sh
curl -i http://127.0.0.1:8000/health
# HTTP/1.1 200 OK
# content-type: application/json
#
# {"status":"ok"}
```

The interactive OpenAPI UI is at `http://127.0.0.1:8000/docs`. Its
**Authorize** button takes the `access_token` from signup or login; after that,
`GET /auth/me` works from the UI.

## Configuration

| Variable | Required | Effect |
|---|---|---|
| `JWT_SECRET` | yes, for the server | HS256 signing secret for access tokens. No default; at least 32 characters. The server refuses to start without it (see above). The test suite sets its own value in `tests/conftest.py`, so it is not needed for `uv run pytest`. Changing it invalidates every token issued before — that is the only way to log everyone out. |
| `DATABASE_URL` | no | SQLAlchemy URL of the database, see [Database](#database). |
| `CORS_ORIGINS` | no | Comma-separated browser origins allowed to call the API (`Authorization` and `Content-Type` headers, all API methods). Default `http://localhost:3000`, the Next.js dev server. |
| `OPENAI_API_KEY` | only for the AI routes | OpenAI API key (Chat Completions, JSON mode). Without any AI key every `/ai/...` route answers `503` and everything else keeps working. |
| `OPENAI_MODEL` | no | OpenAI model name, default `gpt-4.1-mini`. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | no | Alternative provider (Google Gemini, default `gemini-2.5-flash`). OpenAI is used when both keys are set; `AI_PROVIDER=openai\|gemini` forces one. |

Generate a secret:

```sh
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

There is no `.env` file handling; export the variable in the shell that runs
the server.

## Authentication

Accounts are email + password. Passwords are stored as bcrypt hashes (cost
12) and never returned by any route. Signing up or logging in returns an HS256
JWT that expires after **24 hours**; send it as `Authorization: Bearer <token>`
on protected routes. There is no refresh token and no logout endpoint —
"logout" is the client discarding its token, and rotating `JWT_SECRET` revokes
every token at once.

Request rules: the email is trimmed and lower-cased before it is stored or
looked up (so `Ada@Example.com` and `ada@example.com` are the same account) and
must look like `name@domain.tld`; the password must be 8–72 bytes of UTF-8 and
is used exactly as sent; the display name is trimmed and must be 1–100
characters. Invalid input gets FastAPI's standard `422` body.

Sign up (creates the account and logs it in):

```sh
curl -i http://127.0.0.1:8000/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email": "ada@example.com", "password": "correct horse", "display_name": "Ada"}'
# HTTP/1.1 201 Created
#
# {"access_token":"eyJ...","token_type":"bearer","user":{"id":1,"email":"ada@example.com","display_name":"Ada","created_at":"2026-09-17T10:15:30.123456Z"}}
```

Signing up again with the same email (any case, surrounding whitespace ignored):

```sh
curl -i http://127.0.0.1:8000/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email": "ADA@example.com", "password": "another one", "display_name": "Ada"}'
# HTTP/1.1 409 Conflict
#
# {"detail":"Email already registered"}
```

Log in:

```sh
curl -i http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "ada@example.com", "password": "correct horse"}'
# HTTP/1.1 200 OK
#
# {"access_token":"eyJ...","token_type":"bearer","user":{"id":1,"email":"ada@example.com","display_name":"Ada","created_at":"2026-09-17T10:15:30.123456Z"}}
```

A wrong password and an unknown email get the same answer:

```sh
curl -i http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "ada@example.com", "password": "wrong horse"}'
# HTTP/1.1 401 Unauthorized
# www-authenticate: Bearer
#
# {"detail":"Invalid email or password"}
```

Fetch the current user with the token from signup or login:

```sh
TOKEN=$(curl -s http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "ada@example.com", "password": "correct horse"}' \
  | uv run python -c "import json, sys; print(json.load(sys.stdin)['access_token'])")

curl -i http://127.0.0.1:8000/auth/me -H "Authorization: Bearer $TOKEN"
# HTTP/1.1 200 OK
#
# {"id":1,"email":"ada@example.com","display_name":"Ada","created_at":"2026-09-17T10:15:30.123456Z"}
```

Every authentication failure is `401 Unauthorized` with a
`www-authenticate: Bearer` header (never `403`):

```sh
curl -i http://127.0.0.1:8000/auth/me
# HTTP/1.1 401 Unauthorized
# www-authenticate: Bearer
#
# {"detail":"Not authenticated"}

curl -i http://127.0.0.1:8000/auth/me -H "Authorization: Bearer not.a.jwt"
# HTTP/1.1 401 Unauthorized
# www-authenticate: Bearer
#
# {"detail":"Invalid or expired token"}
```

`Not authenticated` means the `Authorization: Bearer <token>` header is
missing or malformed; `Invalid or expired token` covers a bad signature, a
token signed with a previous `JWT_SECRET`, an expired token, and a token whose
user no longer exists.

Timestamps in responses (`created_at`) are ISO 8601 in UTC with an explicit
`Z` suffix.

Later routers protect a route with the same dependency:

```python
from fastapi import Depends
from app.models import User
from app.services.auth import get_current_user

@router.get("/boards")
def list_boards(user: User = Depends(get_current_user)) -> ...:
    ...
```

## Boards and columns

Every route needs `Authorization: Bearer <token>`. A board is visible to its
owner and to users with a `board_members` row; anyone else gets `404` (ids
are not enumerable). A member who is not the owner gets `403` on owner-only
actions.

| Method | Path | Body | Result |
|---|---|---|---|
| `GET` | `/boards` | — | the caller's boards, oldest first, each with `role` (`owner`/`member`) |
| `POST` | `/boards` | `{"name": "..."}` | `201`; also creates the owner membership and the columns "To Do", "In Progress", "Done" |
| `GET` | `/boards/{board_id}` | — | the board plus `columns` ordered by `position` |
| `PATCH` | `/boards/{board_id}` | `{"name": "..."}` | rename (any member) |
| `DELETE` | `/boards/{board_id}` | — | `204` (owner only); members, columns, cards, labels cascade |
| `POST` | `/boards/{board_id}/columns` | `{"name": "..."}` | `201`, appended at the end |
| `PATCH` | `/columns/{column_id}` | `name` and/or `position` | the updated column |
| `DELETE` | `/columns/{column_id}` | — | `204`; `409` if the column still holds cards |

Names are trimmed and must be 1–100 characters. Column `position` is 0-based
and kept contiguous per board; a `position` past the end is `422`. Deleting a
column with cards is refused (`409`) rather than moving the cards — see the
docstring in `app/routers/columns.py`.

```sh
curl -s http://127.0.0.1:8000/boards -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"name": "Roadmap"}'
# {"id":1,"name":"Roadmap","owner_id":1,"role":"owner","created_at":"...Z","updated_at":"...Z","columns":[{"id":1,"board_id":1,"name":"To Do","position":0,"created_at":"...Z"},...]}
```

## Members and invites

| Method | Path | Who | Body | Result |
|---|---|---|---|---|
| `POST` | `/boards/{board_id}/invite` | owner | — | `{"board_id", "invite_token", "invite_path"}`; generated on first call, permanent afterwards |
| `POST` | `/invite/{token}/join` | any signed-in user | — | joins as `member`; `{"board", "joined"}`, `joined: false` when already a member; `404` for an unknown token |
| `GET` | `/boards/{board_id}/members` | member | — | owner first, then members in joining order, each with `email` and `display_name` |
| `POST` | `/boards/{board_id}/members` | owner | `{"email": "..."}` | adds an existing user directly: `201` when added, `200` when already a member, `404` for an unknown email |
| `DELETE` | `/boards/{board_id}/members/{user_id}` | owner | — | `204`; `409` for the owner; cards on the board assigned to that user are unassigned |

The invite link is permanent — there is no regeneration or revocation in
the MVP. `invite_path` is the frontend route (`/invite/<token>`) the link
should point at.

> **Schema change (issue #11):** `boards.invite_token` was added. On SQLite, `create_all`
> does not alter existing tables, so delete any local `mini_kanban.db`
> created before this change and restart the server.

## Dashboard

`GET /boards/{board_id}/dashboard` (members only) returns the four board
metrics and nothing else — no trends or timelines:

```json
{"board_id": 1, "total": 3,
 "by_column": [{"column_id": 1, "name": "To Do", "position": 0, "count": 2}, ...],
 "overdue": 1, "done": 1, "progress_percent": 33.3}
```

- `by_column` lists every column in position order, zero counts included.
- `overdue` counts cards with `due_date` in the past (UTC) that are not in a
  Done column.
- `progress_percent` is `done / total * 100` rounded to one decimal, `0` when
  the board has no cards.
- **A column is "Done" when its name, trimmed and lower-cased, is `done`.**
  The default "Done" column qualifies; renaming it to "Shipped" stops it
  counting, and any additional column named "done" counts too. There is no
  per-column flag — the name is the only signal.

## Cards and labels

Same access rule as boards: members only, `404` otherwise.

| Method | Path | Body | Result |
|---|---|---|---|
| `GET` | `/boards/{board_id}/cards` | query: `q`, `column_id`, `priority`, `assignee_id` | the board's cards, ordered by column position then card position; filters combine with AND |
| `POST` | `/boards/{board_id}/cards` | `title`, `column_id`; optional `description`, `priority`, `due_date`, `assignee_id`, `parent_card_id`, `label_ids`, `position` | `201` |
| `GET` | `/cards/{card_id}` | — | the card with `labels` and `checklist_items` |
| `PATCH` | `/cards/{card_id}` | any of the fields above | the updated card |
| `DELETE` | `/cards/{card_id}` | — | `204`; children are detached, checklist and comments removed |
| `GET` | `/boards/{board_id}/labels` | — | the board's labels |
| `POST` | `/boards/{board_id}/labels` | `{"name": "..."}` | `201`; `409` if the name exists on the board |
| `PATCH` | `/labels/{label_id}` | `{"name": "..."}` | the renamed label |
| `DELETE` | `/labels/{label_id}` | — | `204`; the label is removed from every card |

- **Search and filter** (`GET /boards/{board_id}/cards`): `q` is a
  case-insensitive substring match on title *or* description (`%` and `_`
  are matched literally; a blank `q` is ignored); `column_id`, `priority`
  and `assignee_id` match exactly. All given filters must hold. There are
  no label or due-date filters and no saved filters.
- `priority` is `low`, `medium` (default) or `high`. `due_date` is ISO 8601;
  an offset is converted to UTC, no offset is taken as UTC.
- `column_id`, `assignee_id` (must be a board member), `parent_card_id`
  (must be a card on the same board and not the card itself or one of its
  descendants) and `label_ids` (must be the board's labels) are checked;
  anything off the board is `422`.
- **Moving:** `PATCH` with `column_id` moves the card to that column
  (appended, or at `position` when given); `position` alone reorders within
  the current column. Positions are 0-based and contiguous per column.
- `label_ids` replaces the whole set; `[]` detaches everything.
- Explicit `null` clears `due_date`, `assignee_id` or `parent_card_id`.

```sh
curl -s http://127.0.0.1:8000/boards/1/cards -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"title": "Write tests", "column_id": 1, "priority": "high"}'

curl -s -X PATCH http://127.0.0.1:8000/cards/1 -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"column_id": 3, "position": 0}'
```

## Checklists

Members only, `404` otherwise. The card detail (`GET /cards/{card_id}`)
carries `checklist_items` ordered by `position`.

| Method | Path | Body | Result |
|---|---|---|---|
| `GET` | `/cards/{card_id}/checklist` | — | the card's items ordered by `position` |
| `POST` | `/cards/{card_id}/checklist` | `{"content": "..."}` | `201`, new item appended at the end |
| `PATCH` | `/checklist/{item_id}` | any of `content`, `completed`, `position` | the updated item |
| `DELETE` | `/checklist/{item_id}` | — | `204`, remaining items renumbered |

Checklists are flat (no nesting). `content` is trimmed and must be 1–500
characters. `position` is 0-based and kept contiguous per card: moving an
item to index `n` shifts the others, and a `position` past the end is a
`422`. A `PATCH` with no fields is also a `422`.

```sh
curl -s http://127.0.0.1:8000/cards/1/checklist -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"content": "Write the test"}'
# {"id":1,"card_id":1,"content":"Write the test","completed":false,"position":0}

curl -s -X PATCH http://127.0.0.1:8000/checklist/1 -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"completed": true, "position": 0}'
# {"id":1,"card_id":1,"content":"Write the test","completed":true,"position":0}
```

## Comments

Same access rule as checklists: every route needs a bearer token and the
caller must belong to the card's board (`404` otherwise).

| Method | Path | Body | Result |
|---|---|---|---|
| `GET` | `/cards/{card_id}/comments` | — | comments oldest first, each with `author.id` and `author.display_name` |
| `POST` | `/cards/{card_id}/comments` | `{"content": "..."}` | `201`, the new comment |
| `PATCH` | `/comments/{comment_id}` | `{"content": "..."}` | the updated comment (`updated_at` moves) |
| `DELETE` | `/comments/{comment_id}` | — | `204` |

Only the author may `PATCH` or `DELETE` a comment: another member of the
board gets `403`. `content` is trimmed and must be 1–5000 characters.

```sh
curl -s http://127.0.0.1:8000/cards/1/comments -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"content": "Looks good to me"}'
# {"id":1,"card_id":1,"author":{"id":1,"display_name":"Ada"},"content":"Looks good to me","created_at":"2026-09-17T10:15:30.123456Z","updated_at":"2026-09-17T10:15:30.123456Z"}
```

## AI card actions

`POST /ai/card/{card_id}/improve`, `.../prioritize`, `.../estimate` and
`.../summarize` (members only) ask the model (OpenAI, or Gemini) about **that card's fields only**
(title, description, priority, due date) and return a preview. **Nothing is
written** — to apply a suggestion the client sends a normal
`PATCH /cards/{card_id}` after the user approves.

| Action | Response |
|---|---|
| `improve` | `{"text", "title", "description"}` — a rewritten title and description |
| `prioritize` | `{"text", "priority"}` — `low`, `medium` or `high` |
| `estimate` | `{"text", "size", "time_estimate"}` — `Small`/`Medium`/`Large` and e.g. `"2 hours"` |
| `summarize` | `{"text"}` |
| `breakdown` | `{"text", "tasks": [{"title", "description"}, ...]}` — proposed child tasks |

`text` is the model's natural-language explanation.

**Applying a breakdown** is the one AI route that writes:
`POST /ai/card/{card_id}/breakdown/apply` with `{"tasks": [{"title", "description"}, ...]}`
(the list as the user edited it, 1–20 items) creates the children with
`parent_card_id` set, in the parent's column, appended in order, and
returns them (`201`). It never calls the model, so it also works without
`GEMINI_API_KEY`.

**Natural-language creation:** `POST /ai/create-task` with
`{"board_id": 1, "text": "Fix the login redirect, urgent, by Friday"}` returns
`{"text", "title", "description", "priority", "due_date"}` — a proposal
shaped like a card body without `column_id`. Nothing is saved; after the
user approves, the client posts it (plus the chosen `column_id`) to
`POST /boards/{board_id}/cards`. There is deliberately no
`create-task/apply`. Relative deadlines are resolved against today's UTC
date, which the prompt includes. Errors: `503` when
no AI key is set, `502` when the provider cannot be reached or replies
with something that does not fit the shape above.

The client lives in `app/services/ai.py` behind a one-method `AIClient`
interface; tests override the `get_ai_client` dependency with a fake and
never call the network.

## Docker

`Dockerfile` builds a two-stage image: uv resolves `uv.lock` into a virtualenv,
and a `python:3.14-slim` runtime carries that venv plus `app/`, `alembic/` and
`scripts/`, running as the non-root `app` user on port `8000`.
`docker-entrypoint.sh` runs `alembic upgrade head` first whenever
`DATABASE_URL` is not SQLite, then execs the command (uvicorn by default, or
e.g. `python scripts/seed.py`). The image has a `HEALTHCHECK` on `/health`.

```sh
docker build -t mini-kanban-backend .
docker run --rm -p 8000:8000 -e JWT_SECRET=$JWT_SECRET \
  -e DATABASE_URL=postgresql+psycopg://kanban:kanban@host.docker.internal:5433/kanban \
  mini-kanban-backend
```

The root `docker-compose.yml` wires this to Postgres; see the root README.

## Database

Two backends, chosen by the `DATABASE_URL` environment variable (a full
SQLAlchemy URL):

| `DATABASE_URL` | Effect |
|---|---|
| unset (default) | `sqlite:///./mini_kanban.db` — the file `mini_kanban.db` in `backend/` (relative to the working directory, which is `backend/` for every command here) |
| `sqlite:///path/to/file.db` | a SQLite file at that path |
| `sqlite://` or `sqlite:///:memory:` | an in-memory database that lives only as long as the process (what the unit tests use) |
| `postgresql+psycopg://user:pass@host:5432/dbname` | Postgres through psycopg 3 — what Docker Compose and deployments use |

**SQLite** is the zero-setup path. The file and its tables are created the
first time the server starts (`app/main.py` calls `prepare_database()` in its
`lifespan`, which runs `create_all()` on SQLite). `create_all` only adds
missing tables, so after changing anything in `app/models/` delete the file
and restart:

```sh
rm mini_kanban.db
uv run uvicorn app.main:app --reload
```

**Postgres** gets its schema from Alembic migrations in `alembic/`. On
startup `prepare_database()` runs `alembic upgrade head`, so a fresh
database is migrated by simply starting the server (or the seed script).
To run migrations by hand, or to try it against a throwaway container:

```sh
docker run -d --name mk-pg -e POSTGRES_USER=kanban -e POSTGRES_PASSWORD=kanban -e POSTGRES_DB=kanban -p 5433:5432 postgres:17
export DATABASE_URL=postgresql+psycopg://kanban:kanban@127.0.0.1:5433/kanban
uv run alembic upgrade head     # apply every migration
uv run alembic current          # show the applied revision
uv run alembic check            # fail if the models and the migrations disagree
```

After a model change, generate a migration against a database that is at
`head`, read the generated file (autogenerate misses renames and some
constraint changes), then commit it together with the model change:

```sh
uv run alembic revision --autogenerate -m "add cards.estimate"
uv run alembic upgrade head
uv run alembic check
```

`alembic.ini` holds no connection URL; `alembic/env.py` reads `DATABASE_URL`.
Migrations are never run on SQLite, and `alembic check` against SQLite is not
meaningful (the column types differ).

The schema is one table per model in `app/models/`:
`users`, `boards`, `board_members`, `columns`, `cards`, `labels`,
`card_labels`, `checklist_items`, `comments`, `activities`, plus Alembic's
`alembic_version` on Postgres. To list the tables in the local SQLite file:

```sh
uv run python -c "import sqlite3; print(sorted(r[0] for r in sqlite3.connect('mini_kanban.db').execute(\"select name from sqlite_master where type='table'\")))"
```

Timestamps (`created_at`, `updated_at`, `due_date`) are stored as naive UTC
datetimes on both backends (`TIMESTAMP WITHOUT TIME ZONE` on Postgres); use
`app.database.utcnow()` whenever you need "now".

## Run the tests

All tests:

```sh
uv run pytest
```

One test file:

```sh
uv run pytest tests/test_health.py
```

Tests use `fastapi.testclient.TestClient` in-process, so no server needs to be
running. `tests/conftest.py` sets `DATABASE_URL` to the in-memory `sqlite://`
and a fixed `JWT_SECRET` before the app is imported, so the suite never creates
`mini_kanban.db` and does not need any variable from your shell. Each test that
needs a database gets a fresh, empty schema from the `session` fixture; the
`client` fixture gives a `TestClient` whose requests use that same session.
bcrypt runs at cost 4 under the tests (one test checks the production cost 12)
so the suite stays fast.

### Integration tests (Postgres)

`tests/integration/` runs the same app against a real Postgres: the Alembic
migrations from empty to `head` (and `alembic check` for drift), the seed,
cascades and the unique email index, and the signup → board → card → move →
dashboard journey over HTTP. They need `TEST_DATABASE_URL`; without it they
are **skipped**, so a plain `uv run pytest` is still a SQLite-only run.

```sh
make -C .. test-integration      # starts the Compose db on host port 5433 and runs them
# or, against any Postgres you are happy to have WIPED:
TEST_DATABASE_URL=postgresql+psycopg://kanban:kanban@127.0.0.1:5433/kanban uv run pytest tests/integration
```

See [`docs/testing.md`](../docs/testing.md) for the whole test pyramid.
