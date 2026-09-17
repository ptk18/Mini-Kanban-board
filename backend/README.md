# Mini Kanban — backend

FastAPI backend for the Mini Kanban board. It currently serves a single
smoke-test endpoint, `GET /health`, and defines the SQLite database layer
(SQLAlchemy 2.x models for users, boards, columns, cards, labels, checklist
items, comments and activity). There is no auth or business logic yet.

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

```sh
uv run uvicorn app.main:app --reload
```

Uvicorn prints the listening address (`http://127.0.0.1:8000` by default).

`/health` is the smoke-test endpoint:

```sh
curl -i http://127.0.0.1:8000/health
# HTTP/1.1 200 OK
# content-type: application/json
#
# {"status":"ok"}
```

The interactive OpenAPI UI is at `http://127.0.0.1:8000/docs`.

## Database

The app uses SQLite through SQLAlchemy. The location comes from the
`DATABASE_URL` environment variable, a full SQLAlchemy URL:

| `DATABASE_URL` | Effect |
|---|---|
| unset (default) | `sqlite:///./mini_kanban.db` — the file `mini_kanban.db` in `backend/` (relative to the working directory, which is `backend/` for every command here) |
| `sqlite:///path/to/file.db` | a SQLite file at that path |
| `sqlite://` or `sqlite:///:memory:` | an in-memory database that lives only as long as the process (what the tests use) |

The database file and all of its tables are created automatically the first
time the server starts (`app/main.py` runs `create_all()` in its `lifespan`).
Nothing is created just by importing the code, and starting the server again
against an existing file is fine — `create_all` only adds tables that are
missing. `*.db` is git-ignored, so the file is never committed.

There is no migration tool (no Alembic). `create_all` does **not** alter
tables that already exist, so after changing anything in `app/models/`,
delete the file and restart to get the new schema:

```sh
rm mini_kanban.db
uv run uvicorn app.main:app --reload
```

The schema is one table per model in `app/models/`:
`users`, `boards`, `board_members`, `columns`, `cards`, `labels`,
`card_labels`, `checklist_items`, `comments`, `activities`. To list the tables
in the local file:

```sh
uv run python -c "import sqlite3; print(sorted(r[0] for r in sqlite3.connect('mini_kanban.db').execute(\"select name from sqlite_master where type='table'\")))"
```

Timestamps (`created_at`, `updated_at`, `due_date`) are stored as naive UTC
datetimes; use `app.database.utcnow()` whenever you need "now".

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
before the app is imported, so the suite never creates `mini_kanban.db`, and
each test that needs a database gets a fresh, empty schema from the `session`
fixture.
