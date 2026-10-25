# Testing

Three layers, each proving something the others cannot. `make test` runs all
of them and fails if any layer fails; `make test-unit` runs only the fast,
Docker-free ones.

| Layer | Where | Runner | Needs | Command | Proves |
|---|---|---|---|---|---|
| Backend unit | `backend/tests/*.py` | pytest, `TestClient`, in-memory SQLite | nothing | `make test-backend` / `cd backend && uv run pytest` | Every route's contract: status codes, bodies, permissions, positions, validation. Fast (seconds), runs on every save. |
| Frontend unit | `frontend/tests/*.test.tsx` | Vitest + React Testing Library (jsdom), API client mocked | nothing | `make test-frontend` / `cd frontend && npm test` | Components and page flows render and call the API client correctly for given data. |
| Backend integration | `backend/tests/integration/test_pg_*.py` | pytest against a real Postgres | Docker (the Compose `db` service) | `make test-integration` | The Alembic migrations produce the schema the models expect (and have not drifted), Postgres-specific behaviour (cascades, unique index, naive timestamps), the seed, and the signup → board → card → move → dashboard journey through HTTP against the production database engine. |
| Browser end-to-end | `frontend/e2e/*.spec.ts` | Playwright (Chromium) against the full Compose stack | Docker + `npx playwright install chromium` | `make test-e2e` | The built frontend image, the backend image and Postgres work together as a user sees them: sign up, create a board, add a card, reload and still see it, open the dashboard; a wrong password is rejected. |

## Commands

```sh
make test               # everything (unit → integration → e2e); exits non-zero on any failure
make test-unit          # backend pytest (SQLite) + frontend vitest, no Docker
make test-integration   # starts the Compose db (host port 5433), runs backend/tests/integration
make test-e2e           # builds + starts the whole Compose stack, runs Playwright, stops the stack
```

One-time setup for the browser tests:

```sh
cd frontend && npx playwright install chromium
```

## How the layers are kept apart

- **Unit tests never need Postgres.** `backend/tests/conftest.py` pins
  `DATABASE_URL=sqlite://`; the integration directory's own `conftest.py`
  skips every test there unless `TEST_DATABASE_URL` is set, so a plain
  `uv run pytest` reports them as `skipped`, never `failed`.
- **Integration tests own the migrations.** The module-scoped `pg_engine`
  fixture drops the schema and runs `alembic upgrade head`; `pg_session`
  truncates every table before each test. The app is exercised through
  `TestClient` with `get_db` overridden to the Postgres session, exactly as
  the unit suite does with SQLite.
- **Playwright files live in `frontend/e2e/`**, excluded from Vitest in
  `vitest.config.mts`; `playwright.config.ts` points at `E2E_BASE_URL`
  (default `http://localhost:3000`). Each run signs up a fresh user, so it
  does not depend on, or disturb, existing data.

## Running integration tests against another Postgres

```sh
cd backend
TEST_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname uv run pytest tests/integration
```

The database is **wiped** (`DROP SCHEMA public CASCADE`) at the start of each
module. Never point it at a database with data you want.

## Where the conventions live

Writing conventions (fixtures, query priority, what to assert) are in
[`_docs/testing-guidelines.md`](../_docs/testing-guidelines.md). This page is
about running; that page is about writing.

## CI

`.github/workflows/ci.yml` runs four jobs on every pull request and push to
`main`: **backend** (unit on SQLite, integration against a `postgres:17`
service container, `alembic check`), **frontend** (lint, typecheck, Vitest),
**docker** (both images build, layer cache in GitHub Actions), **e2e** (the
Compose stack on the runner + Playwright; the HTML report is uploaded on
failure). No secrets are involved.

**Branch protection.** `main` should require the four checks before a merge:
repository *Settings → Branches → Add branch ruleset* (or classic protection
rule) for `main` → *Require status checks to pass* → select `Backend (unit +
Postgres integration)`, `Frontend (lint, typecheck, unit)`, `Docker images
build`, `End-to-end (Compose stack + Playwright)`. This needs admin rights on
the repository, so it is a one-time click by the owner; with the setting on, a
red check blocks merging. See [`release-process.md`](release-process.md) for
what happens after CI is green.
