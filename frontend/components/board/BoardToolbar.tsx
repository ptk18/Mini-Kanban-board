"use client";

import type { CardFilters, Column, Member, Priority } from "@/lib/api";
import { SecondaryButton, TextInput } from "@/components/ui";

const selectClass =
  "rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-300";

export function activeFilterCount(filters: CardFilters): number {
  return [
    Boolean(filters.q?.trim()),
    filters.column_id != null,
    Boolean(filters.priority),
    filters.assignee_id != null,
  ].filter(Boolean).length;
}

export function BoardToolbar({
  filters,
  columns,
  members,
  onChange,
}: {
  filters: CardFilters;
  columns: Column[];
  members: Member[];
  onChange: (next: CardFilters) => void;
}) {
  const active = activeFilterCount(filters);
  const set = (patch: Partial<CardFilters>) => onChange({ ...filters, ...patch });

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <TextInput
        type="search"
        aria-label="Search cards"
        placeholder="Search title or description"
        value={filters.q ?? ""}
        onChange={(e) => set({ q: e.target.value })}
        className="w-64"
      />
      <select
        aria-label="Filter by column"
        className={selectClass}
        value={filters.column_id ?? ""}
        onChange={(e) => set({ column_id: e.target.value ? Number(e.target.value) : null })}
      >
        <option value="">All columns</option>
        {columns.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <select
        aria-label="Filter by priority"
        className={selectClass}
        value={filters.priority ?? ""}
        onChange={(e) => set({ priority: e.target.value as Priority | "" })}
      >
        <option value="">Any priority</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <select
        aria-label="Filter by assignee"
        className={selectClass}
        value={filters.assignee_id ?? ""}
        onChange={(e) => set({ assignee_id: e.target.value ? Number(e.target.value) : null })}
      >
        <option value="">Anyone</option>
        {members.map((m) => (
          <option key={m.user_id} value={m.user_id}>
            {m.display_name}
          </option>
        ))}
      </select>
      {active > 0 && (
        <>
          <span className="text-xs text-zinc-400" data-testid="active-filter-count">
            {active} {active === 1 ? "filter" : "filters"} active
          </span>
          <SecondaryButton onClick={() => onChange({})}>Clear</SecondaryButton>
        </>
      )}
    </div>
  );
}
