# Mini Kanban — frontend

Next.js (App Router) + TypeScript + Tailwind CSS frontend for the Mini Kanban
board: sign up, log in, log out, and the board list. The board screen itself
is issue #23.

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
Escape cancels), delete with confirmation (owner only) — and is guarded:
without a valid token it redirects to `/login`. **Log out** in the header
discards the token.

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

## Lint, typecheck, build

```bash
npm run lint
npm run typecheck
npm run build
```

## Stack

Exact installed versions (from `package-lock.json`):

- `next` 16.3.5
- `react` 19.2.8
- `tailwindcss` 4.3.3 (CSS-first config in `app/globals.css`; no `tailwind.config.*`)
- `vitest` 5.0.1, with `@testing-library/react` 16.3.3 and `jsdom` 30.1.0

The test setup follows the Next.js Vitest guide:
https://nextjs.org/docs/app/guides/testing/vitest
(one deviation: the `test` script is `vitest run`, so `npm test` never enters
watch mode).

## Layout

- `app/layout.tsx` — root layout, dark theme (`bg-zinc-950` / `text-zinc-100`), wraps everything in `AuthProvider`
- `app/page.tsx` — landing page (`/`) with links
- `app/login/`, `app/signup/` — auth pages
- `app/boards/page.tsx` — board list (guarded); `app/boards/[id]/page.tsx` — placeholder board screen (#23)
- `lib/api.ts` — typed API client: `signup`, `login`, `me`, `listBoards`, `createBoard`, `getBoard`, `renameBoard`, `deleteBoard`; token in `localStorage` (`mini-kanban.token`); non-2xx → `ApiError { status, detail }`
- `lib/auth.tsx` — `AuthProvider` / `useAuth()`: restores the session from the stored token on load (any `401` clears it), `login`, `signup`, `logout`
- `lib/validation.ts` — client-side mirrors of the backend's email/password/display-name rules
- `components/RequireAuth.tsx` — route guard (redirects to `/login`); `AppHeader.tsx` — brand link, user name, log out
- `components/LoginForm.tsx`, `SignupForm.tsx`, `BoardList.tsx`, `Field.tsx`, `ui.tsx`
- `app/globals.css` — Tailwind import and `color-scheme: dark`
- `tests/` — Vitest tests: `page.test.tsx`, `login-form.test.tsx`, `board-list.test.tsx`; `setup.ts` registers Testing Library cleanup
- `vitest.config.mts` — Vitest config; `@/*` resolves to `./*` via `vite-tsconfig-paths`
