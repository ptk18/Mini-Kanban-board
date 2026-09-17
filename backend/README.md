# Mini Kanban — backend

FastAPI backend for the Mini Kanban board. It serves the smoke-test endpoint
`GET /health`, email/password authentication with JWT bearer tokens
(`POST /auth/signup`, `POST /auth/login`, `GET /auth/me`), and defines the
SQLite database layer (SQLAlchemy 2.x models for users, boards, columns, cards,
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
and a fixed `JWT_SECRET` before the app is imported, so the suite never creates
`mini_kanban.db` and does not need any variable from your shell. Each test that
needs a database gets a fresh, empty schema from the `session` fixture; the
`client` fixture gives a `TestClient` whose requests use that same session.
bcrypt runs at cost 4 under the tests (one test checks the production cost 12)
so the suite stays fast.
