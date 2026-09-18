"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import * as api from "@/lib/api";
import type { BoardDetail } from "@/lib/api";
import { AppHeader } from "@/components/AppHeader";
import { RequireAuth } from "@/components/RequireAuth";
import { ErrorText } from "@/components/ui";

/** Placeholder board screen; the real board page is issue #23. */
export default function BoardPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const valid = Number.isInteger(id);
  const [board, setBoard] = useState<BoardDetail | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const error = valid ? fetchError : "Not found";

  useEffect(() => {
    if (!valid) return;
    api
      .getBoard(id)
      .then(setBoard)
      .catch((e) => setFetchError(e instanceof api.ApiError ? e.detail : "Could not reach the server"));
  }, [id, valid]);

  return (
    <RequireAuth>
      <AppHeader />
      <main className="flex flex-col gap-6 p-8">
        {error && <ErrorText>{error}</ErrorText>}
        {board && (
          <>
            <h1 className="text-3xl font-semibold tracking-tight">{board.name}</h1>
            <ul className="flex gap-4 overflow-x-auto">
              {board.columns.map((column) => (
                <li
                  key={column.id}
                  className="w-72 shrink-0 rounded-lg bg-zinc-900 p-3 text-sm font-medium uppercase tracking-wide text-zinc-400"
                >
                  {column.name}
                </li>
              ))}
            </ul>
          </>
        )}
      </main>
    </RequireAuth>
  );
}
