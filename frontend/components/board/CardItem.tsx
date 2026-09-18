"use client";

import type { Card, Column, Member } from "@/lib/api";

const priorityClass = {
  high: "text-red-400",
  medium: "text-amber-400",
  low: "text-zinc-400",
} as const;

export function isOverdue(card: Card, column: Column | undefined, now = new Date()): boolean {
  if (!card.due_date) return false;
  if (column && column.name.trim().toLowerCase() === "done") return false;
  return new Date(card.due_date) < now;
}

export function CardItem({
  card,
  columns,
  members,
  onMove,
}: {
  card: Card;
  columns: Column[];
  members: Member[];
  onMove: (columnId: number) => void;
}) {
  const column = columns.find((c) => c.id === card.column_id);
  const assignee = members.find((m) => m.user_id === card.assignee_id);
  const overdue = isOverdue(card, column);

  return (
    <li className="flex flex-col gap-1.5 rounded-md bg-zinc-800 px-3 py-2 transition-colors hover:bg-zinc-700">
      <p className="truncate text-sm font-medium text-zinc-100" title={card.title}>
        {card.title}
      </p>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-zinc-400">
        <span className={`font-medium ${priorityClass[card.priority]}`}>{card.priority}</span>
        {card.due_date && (
          <span className={overdue ? "text-red-400" : undefined}>
            {overdue ? "overdue " : "due "}
            {card.due_date.slice(0, 10)}
          </span>
        )}
        {card.labels.map((label) => (
          <span key={label.id} className="rounded bg-zinc-900 px-1.5 py-0.5">
            {label.name}
          </span>
        ))}
        {assignee && <span className="ml-auto">{assignee.display_name}</span>}
      </div>
      <select
        aria-label={`Move ${card.title}`}
        className="rounded border border-zinc-700 bg-zinc-900 px-1.5 py-1 text-xs text-zinc-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-300"
        value={card.column_id}
        onChange={(e) => onMove(Number(e.target.value))}
      >
        {columns.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
    </li>
  );
}
