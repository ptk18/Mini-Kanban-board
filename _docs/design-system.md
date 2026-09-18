# Design system

Visual direction from `plan.md` §10: **dark developer tool + minimal** — dark
theme, minimal visual noise, clear typography, compact cards, strong
keyboard/mouse usability, simple navigation, minimal animations. The board is
the primary screen.

Everything below describes what is in `frontend/` today (`app/globals.css`,
`app/layout.tsx`, `app/page.tsx`) plus the tokens the upcoming screens should
use. Tailwind CSS 4 is configured CSS-first (`@import "tailwindcss"` in
`globals.css`, no `tailwind.config.*`), so tokens are Tailwind utility classes
and the `zinc` palette, not a custom theme file.

## Theme

Dark only. There is no light theme and no toggle.

| Token | Value | Where |
|---|---|---|
| Colour scheme | `color-scheme: dark` on `html` | `globals.css` — native controls (inputs, scrollbars) render dark |
| Page background | `bg-zinc-950` | `layout.tsx` `<body>` |
| Default text | `text-zinc-100` | `layout.tsx` `<body>` |
| Secondary text | `text-zinc-400` | `page.tsx` tagline |
| Text rendering | `antialiased` | `layout.tsx` `<body>` |
| Min height | `min-h-screen` on `<body>` | `layout.tsx` |

Surface and accent tokens for the screens to come (keep to these so the UI
reads as one tool):

| Role | Class |
|---|---|
| Board canvas | `bg-zinc-950` |
| Column surface | `bg-zinc-900` |
| Card surface | `bg-zinc-800`, hover `bg-zinc-700` |
| Borders / dividers | `border-zinc-800` |
| Muted labels, metadata | `text-zinc-400`, `text-zinc-500` |
| Focus ring | `focus-visible:ring-2 ring-zinc-300` (keyboard usability is a §10 requirement — never remove outlines without a visible ring) |
| Priority `high` / `medium` / `low` | `text-red-400` / `text-amber-400` / `text-zinc-400` |
| Overdue due date | `text-red-400` |
| Destructive action | `text-red-400`, confirm before deleting boards, columns, cards |

## Typography

- Font stack: Tailwind's `font-sans` (`ui-sans-serif, system-ui, sans-serif`
  plus emoji fallbacks). No web fonts are loaded; nothing to download and it
  matches the "developer tool" feel of native UI.
- Page heading (`h1`): `text-3xl font-semibold tracking-tight` (as on the home
  page).
- Column header: `text-sm font-medium uppercase tracking-wide text-zinc-400`.
- Card title: `text-sm font-medium text-zinc-100`, single line, truncate.
- Card metadata (due date, assignee, labels): `text-xs text-zinc-400`.
- Body / descriptions: `text-sm`, `leading-relaxed`.

## Spacing and layout

- Page padding: `p-8` on top-level screens (home page uses it); `p-4` inside
  panels and modals.
- Board: horizontal scroll of columns, `gap-4`, each column `w-72` (18 rem)
  and `rounded-lg`.
- Column: `p-3`, cards stacked with `gap-2`; "add card" input at the bottom.
- Card: `rounded-md`, `px-3 py-2`, one-line title, one metadata row. Compact
  by default — no description preview on the board.
- Modal: `max-w-2xl`, `rounded-lg`, `p-6`, `Escape` closes, focus trapped.
- Toolbar (search + filters): a single row, `gap-2`, `text-sm` controls.

## Motion

Minimal: `transition-colors` on hover/focus only. No entrance animations, no
drag-and-drop spring effects beyond the library default.

## Components to keep consistent

- **Button**: `rounded-md px-3 py-1.5 text-sm font-medium`; primary
  `bg-zinc-100 text-zinc-900 hover:bg-white`; secondary
  `bg-zinc-800 text-zinc-100 hover:bg-zinc-700`.
- **Input / select**: `rounded-md border border-zinc-700 bg-zinc-900 px-3
  py-1.5 text-sm` with the focus ring above.
- **Badge** (labels, priority): `rounded px-1.5 py-0.5 text-xs`.
