# Mini Kanban — frontend

Next.js (App Router) + TypeScript + Tailwind CSS skeleton for the Mini Kanban
board. It renders a dark-themed home page at `http://localhost:3000` and has
one Vitest + React Testing Library test.

All commands below are run from `frontend/`.

## Prerequisites

- Node.js `>=20.9.0` (the `engines.node` requirement of `next` 16.3.5)
- npm (ships with Node; 11.x was used here)

## Install

```bash
npm ci
```

## Run the dev server

```bash
npm run dev
```

Open `http://localhost:3000`.

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

- `app/layout.tsx` — root layout, dark theme (`bg-zinc-950` / `text-zinc-100`), title `Mini Kanban`
- `app/page.tsx` — home page (`/`)
- `app/globals.css` — Tailwind import and `color-scheme: dark`
- `tests/` — Vitest tests (`tests/page.test.tsx`)
- `vitest.config.mts` — Vitest config; `@/*` resolves to `./*` via `vite-tsconfig-paths`
