# Testing guidelines

Every statement here is checked against the code as of issue #20. When the
setup changes, change this file in the same commit.

## Where tests live

| App | Directory | Runner | Naming |
|---|---|---|---|
| backend | `backend/tests/` | pytest | `test_<area>.py`, one file per router or concern (`test_auth.py`, `test_boards.py`, `test_cards.py`, `test_ai.py`, `test_seed.py`, …) |
| frontend | `frontend/tests/` | Vitest + React Testing Library (jsdom) | `<thing>.test.tsx` |

There are no end-to-end browser tests.

## How to run them

Backend, from `backend/`:

```sh
uv run pytest                    # the whole suite
uv run pytest tests/test_health.py  # one file
uv run pytest -k "overdue"       # by name
```

Frontend, from `frontend/`:

```sh
npm test                         # vitest run — single pass, never watch mode
npx vitest run tests/page.test.tsx
npm run test:watch               # watch mode, local only
```

Both suites must be green before an issue is closed; QA re-runs them.

## Backend conventions

- **In-process, in-memory.** `tests/conftest.py` sets `DATABASE_URL=sqlite://`
  and a fixed `JWT_SECRET` *before* the app is imported. Tests never start
  uvicorn and never create `mini_kanban.db`.
- **Fixtures** (all in `conftest.py`):
  - `session` — a fresh, empty schema on its own in-memory engine per test.
  - `client` — `fastapi.testclient.TestClient` whose `get_db` is overridden
    to yield that same `session`, so a test can create rows directly and read
    back what a request changed. Created without `with`, so the lifespan does
    not run.
  - `fast_bcrypt` (autouse) — bcrypt cost 4; one test restores cost 12.
  - `fake_ai` — replaces `get_ai_client` with a `FakeAI` that records prompts
    and returns whatever the test queued (a string or an exception). AI tests
    never reach the network.
- **Auth in tests**: create a `User` row directly (`password_hash` can be a
  dummy unless the test logs in) and mint a token with
  `create_access_token(user.id)`; a `headers(user)` helper per file.
- **Per-file `Api` helper**: each router test file wraps the endpoints it
  exercises in a tiny class (`api.create(...)`, `api.patch(...)`) with
  `as_user=` to switch identity. Keeps assertions about status codes and
  bodies readable.
- **Assert the contract, then the database.** Check the status code, the exact
  body (or `.keys()` for large shapes), then re-read rows with
  `session.expire_all()` for anything the request should or should not have
  changed — including "nothing changed" after a rejected request.
- **Permissions in every file**: a non-member gets `404`, a member on an
  owner-only route gets `403`, a missing token gets `401`. Each router file
  has a `test_non_member_is_rejected_on_every_endpoint`-style test.
- **Positions**: reorder tests read back `(title, position)` pairs and assert
  the whole column, not just the moved row.
- **Parametrize** validation cases (`@pytest.mark.parametrize`) instead of
  copy-pasting tests.
- The route-set test in `tests/test_database.py` lists every path and method;
  extend it when adding a route so nothing ships unlisted.
- No warnings: `uv run pytest` must report only `passed`. The single
  `filterwarnings` entry in `pyproject.toml` covers an upstream Starlette
  deprecation and is not to be extended.

## Frontend conventions

- Vitest with `environment: "jsdom"` and `@vitejs/plugin-react`
  (`vitest.config.mts`); `@/` resolves to `frontend/` via
  `vite-tsconfig-paths`.
- Render with `@testing-library/react`'s `render` and query with `screen`.
- **Query priority** (Testing Library's own order): `getByRole` with an
  accessible name first (`screen.getByRole("heading", { level: 1, name:
  "Mini Kanban" })` — the existing test), then `getByLabelText` for form
  fields, `getByText` for static copy, and `getByTestId` only as a last
  resort. If a query needs a test id, first ask whether the element is
  missing a role or label a user would also miss.
- `getBy*` when the element must be there, `queryBy*` to assert absence,
  `findBy*` (async) after an action that triggers a fetch or state update.
- Interact through `@testing-library/user-event`-style APIs (add the package
  when the first interactive test lands) rather than firing raw DOM events.
- Mock the API client at the module boundary (`vi.mock("@/lib/api")`), never
  `fetch` globally; assert on the client call (e.g. the query string built
  from selected filters) and on what the user sees.
- One behaviour per test; name it after the behaviour
  (`"home page renders the Mini Kanban heading"`).

## User-flow tests

Flows (log in → open a board → move a card) are covered as **component tests
of the page that owns the flow**, with the API client mocked to return
fixture data, rather than as browser end-to-end tests:

1. Render the page component with the mocked client.
2. Drive it as a user would (type, click, press `Escape`).
3. Assert the visible result *and* the client call that would have persisted
   it (`expect(api.patchCard).toHaveBeenCalledWith(...)`).

Each flow-shaped issue names its test in the description (e.g. #11's
`/invite/[token]` join-then-redirect, #14's query-string test). Keep flow
tests short; the backend suite already proves the server side.
