"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import type { Dashboard } from "@/lib/api";
import { describeError } from "@/hooks/useBoardData";
import { ErrorText } from "@/components/ui";

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <p className="text-xs uppercase tracking-wide text-zinc-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

export function DashboardMetrics({ data }: { data: Dashboard }) {
  const percent = Math.round(data.progress_percent);
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metric label="Total tasks" value={data.total} />
        <Metric label="Overdue" value={data.overdue} />
        <Metric label="Done" value={data.done} />
        <Metric label="Progress" value={`${data.progress_percent}%`} />
      </div>
      <div>
        <div
          role="progressbar"
          aria-label="Progress"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-2 w-full overflow-hidden rounded bg-zinc-800"
        >
          <div className="h-full bg-zinc-100" style={{ width: `${percent}%` }} />
        </div>
        <p className="mt-1 text-xs text-zinc-400">
          {data.total === 0 ? "No tasks yet." : `${data.done} of ${data.total} tasks done.`}
        </p>
      </div>
      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-zinc-400">Tasks by status</h2>
        <ul className="flex flex-col gap-1 text-sm">
          {data.by_column.map((column) => (
            <li key={column.column_id} className="flex justify-between border-b border-zinc-800 py-1">
              <span>{column.name}</span>
              <span className="text-zinc-400">{column.count}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export function DashboardView({ boardId }: { boardId: number }) {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getDashboard(boardId).then(setData).catch((e) => setError(describeError(e)));
  }, [boardId]);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div className="flex items-center gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">Dashboard</h1>
        <Link href={`/boards/${boardId}`} className="ml-auto text-sm underline-offset-4 hover:underline">
          Back to board
        </Link>
      </div>
      {error && <ErrorText>{error}</ErrorText>}
      {data ? <DashboardMetrics data={data} /> : !error && <p className="text-sm text-zinc-500">Loading…</p>}
    </div>
  );
}
