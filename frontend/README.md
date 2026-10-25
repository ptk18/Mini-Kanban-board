# Mini Kanban — frontend

Next.js (App Router) + TypeScript + Tailwind CSS frontend for the Mini Kanban
board: auth, the board list, the board screen (columns, cards, column
management, search and filters, members and invites), the card modal with
the AI actions, natural-language task creation and the dashboard.

All commands below are run from `frontend/`.

## Prerequisites

- Node.js `>=20.9.0` (the `engines.node` requirement of `next` 16.3.5)
- npm (ships with Node; 11.x was used here)

## Install

```bash
npm ci
```

## Configure

```bash
cp .env.example .env.local   # NEXT_PUBLIC_API_URL, default http://127.0.0.1:8000
```

The backend must allow this origin (`CORS_ORIGINS`, default
`http://localhost:3000` — see `backend/README.md`).

## Run the dev server

```bash
npm run dev
```

Open `http://localhost:3000`. `/signup` creates an account and logs you in;
`/login` for an existing one (the seed accounts from `backend/scripts/seed.py`
work). `/boards` lists your boards — create, rename inline (Enter saves,
Escape cancels), delete with confirmation (owner only). `/boards/[id]` is the
board: columns of compact cards (title, priority, due date — red when
overdue and not in Done — labels, assignee), an **Add card** input per
column, a status dropdown on each card to move it, **Add column** at the
end, drag a card to reorder it or move it to another column, drag the ⋮⋮
handle to reorder columns (the move shows immediately and rolls back if the
server refuses), click a card title to open the card modal — edit every field, labels
(including creating a new one), see the parent, delete, manage the checklist
and comments, and run the **AI** actions (Break down, Improve, Prioritize,
Estimate effort, Summarize): each shows a preview you can edit and **Approve**
(writes through the card `PATCH`, or `breakdown/apply` for child tasks) or
**Discard** (writes nothing; Summarize is read-only; Estimate appends an
"Estimate: …" line to the description). **New task from text** above the
board asks `POST /ai/create-task` for a proposal and opens it in the modal;
**Create card** then goes through the normal card `POST`. The backend needs
an AI key (`OPENAI_API_KEY` or `GEMINI_API_KEY`) for any of this. Escape closes and focus stays inside — click
a column header to rename it, **Delete** with a confirmation that
explains the cards must be moved first. The toolbar searches (`q`) and
filters by column, priority and assignee (AND), with an active-filter count
and **Clear**. **Members** opens the panel (owner: copy invite link, invite
by email, remove); **Dashboard** links to `/boards/[id]/dashboard`. An
invite link (`/invite/[token]`) joins the board and redirects to it,
sending signed-out users to `/login?next=…` first. There are no live
updates: the board refetches after each mutation and when the tab regains
focus. Guarded pages redirect to `/login` without a valid token; **Log out**
in the header discards the token.

## Tests

Run all tests (single pass, never watch mode):

```bash
npm test
```

Run one test file:

```bash
npx vitest run tests/page.test.tsx
```

`npm run test:watch` runs Vitest in watch mode.

### Browser end-to-end tests (Playwright)

`e2e/` holds Playwright specs that drive the real frontend against the real
backend and database (the Docker Compose stack). They are excluded from
Vitest. One-time setup, then run them against a stack that is already up:

```bash
npx playwright install chromium
npm run test:e2e                  # expects http://localhost:3000; override with E2E_BASE_URL
```

`make -C .. test-e2e` builds and starts the stack, runs them and stops it.
See [`docs/testing.md`](../docs/testing.md).

## Lint, typecheck, build

```bash
npm run lint
npm run typecheck
npm run build
```

`next.config.ts` sets `output: "standalone"`, so `npm run build` also emits
`.next/standalone/` (a traced server without `node_modules`); `npm start`
still works for a plain Node deployment.

## Docker

`Dockerfile` is a three-stage build (deps → `next build` → runner on
`node:22-alpine`, non-root `node` user, port `3000`). `NEXT_PUBLIC_API_URL` is
a **build argument**: Next.js inlines `NEXT_PUBLIC_*` values into the browser
bundle, so the image is built for one backend URL — the one the *browser*
will call, not a Compose service name.

```bash
docker build --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 -t mini-kanban-frontend .
docker run --rm -p 3000:3000 mini-kanban-frontend
```

The root `docker-compose.yml` does this for you; see the root README.

## Stack

Exact installed versions (from `package-lock.json`):

- `next` 16.3.5
- `react` 19.2.8
- `tailwindcss` 4.3.3 (CSS-first config in `app/globals.css`; no `tailwind.config.*`)
- `@dnd-kit/core` 6.3, `@dnd-kit/sortable` 10.0, `@dnd-kit/utilities` 3.2 — drag-and-drop (pointer + keyboard)
- `vitest` 5.0.1, with `@testing-library/react` 16.3.3 and `jsdom` 30.1.0

The test setup follows the Next.js Vitest guide:
https://nextjs.org/docs/app/guides/testing/vitest
(one deviation: the `test` script is `vitest run`, so `npm test` never enters
watch mode).

## Layout

- `app/layout.tsx` — root layout, dark theme (`bg-zinc-950` / `text-zinc-100`), wraps everything in `AuthProvider`
- `app/page.tsx` — landing page (`/`) with links
- `app/login/`, `app/signup/` — auth pages
- `app/boards/page.tsx` — board list (guarded); `app/boards/[id]/page.tsx` — board; `app/boards/[id]/dashboard/page.tsx` — dashboard; `app/invite/[token]/page.tsx` — join by invite link
- `lib/api.ts` — typed API client for auth, boards, columns, cards (`buildCardQuery` for the filters), labels, members/invites and the dashboard; token in `localStorage` (`mini-kanban.token`); non-2xx → `ApiError { status, detail }`
- `lib/positions.ts` — pure drop → `{column_id, position}` / column index calculation and the optimistic array helpers (`tests/positions.test.ts`)
- `components/board/dnd.ts` — dnd-kit ids and `data` payloads
- `hooks/useBoardData.ts` — board + filtered cards + members with `refetch()`, refetching on window focus / visibility
- `components/board/` — `BoardView`, `BoardToolbar`, `ColumnView`, `CardItem`, `AddColumnForm`, `MembersPanel`, `DashboardView`; `components/InviteJoin.tsx`
- `components/card/` — `CardModal` (fields, labels, parent, save/delete; `diffCard` builds the PATCH body; new-card mode from a proposal), `AiPanel`, `ChecklistSection`, `CommentsSection`; `components/board/NewTaskForm.tsx`; `hooks/useFocusTrap.ts` (focus trap + Escape)
- `lib/auth.tsx` — `AuthProvider` / `useAuth()`: restores the session from the stored token on load (any `401` clears it), `login`, `signup`, `logout`
- `lib/validation.ts` — client-side mirrors of the backend's email/password/display-name rules
- `components/RequireAuth.tsx` — route guard (redirects to `/login`); `AppHeader.tsx` — brand link, user name, log out
- `components/LoginForm.tsx`, `SignupForm.tsx`, `BoardList.tsx`, `Field.tsx`, `ui.tsx`
- `app/globals.css` — Tailwind import and `color-scheme: dark`
- `tests/` — Vitest tests: `page`, `login-form`, `board-list`, `board-view`, `board-toolbar`, `card-modal`, `ai`, `dashboard`, `invite`, `positions` (`fixtures.ts` shared data; `setup.ts` registers Testing Library cleanup)
- `vitest.config.mts` — Vitest config; `@/*` resolves to `./*` via `vite-tsconfig-paths`
