# Mini Kanban — backend

FastAPI backend for the Mini Kanban board. This is the project skeleton: it
serves a single smoke-test endpoint, `GET /health`, and has no database, auth,
or business logic yet.

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

## Run the tests

All tests:

```sh
uv run pytest
```

One test file:

```sh
uv run pytest tests/test_health.py
```

Tests use `fastapi.testclient.TestClient` in-process, so no server needs to be running.
