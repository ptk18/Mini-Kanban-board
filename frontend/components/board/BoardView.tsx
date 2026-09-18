"use client";

import { useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import type { Card, CardFilters, Column } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { describeError, useBoardData } from "@/hooks/useBoardData";
import { AddColumnForm } from "@/components/board/AddColumnForm";
import { BoardToolbar } from "@/components/board/BoardToolbar";
import { ColumnView } from "@/components/board/ColumnView";
import { MembersPanel } from "@/components/board/MembersPanel";
import { ErrorText, SecondaryButton } from "@/components/ui";

export function BoardView({ boardId }: { boardId: number }) {
  const { user } = useAuth();
  const [filters, setFilters] = useState<CardFilters>({});
  const [showMembers, setShowMembers] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const { board, cards, members, error, loading, refetch } = useBoardData(boardId, filters);

  if (error) return <ErrorText>{error}</ErrorText>;
  if (loading || !board) return <p className="text-sm text-zinc-500">Loading…</p>;

  const columns = [...board.columns].sort((a, b) => a.position - b.position);
  const isOwner = board.role === "owner";

  // Every mutation goes through the API and then refetches (plan §5).
  async function mutate(action: () => Promise<unknown>) {
    try {
      await action();
      setActionError(null);
    } catch (e) {
      setActionError(describeError(e));
      throw new Error(describeError(e));
    } finally {
      await refetch();
    }
  }

  const rename = (column: Column, name: string) => mutate(() => api.updateColumn(column.id, { name }));
  const remove = (column: Column) => mutate(() => api.deleteColumn(column.id));
  const addCard = (column: Column, title: string) =>
    mutate(() => api.createCard(boardId, { title, column_id: column.id }));
  const moveCard = (card: Card, columnId: number) => {
    if (columnId !== card.column_id) void mutate(() => api.updateCard(card.id, { column_id: columnId })).catch(() => {});
  };
  const addColumn = (name: string) => mutate(() => api.createColumn(boardId, name));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{board.name}</h1>
        <nav className="ml-auto flex items-center gap-2 text-sm">
          <Link href={`/boards/${boardId}/dashboard`} className="underline-offset-4 hover:underline">
            Dashboard
          </Link>
          <SecondaryButton onClick={() => setShowMembers((v) => !v)} aria-expanded={showMembers}>
            Members ({members.length})
          </SecondaryButton>
        </nav>
      </div>

      <BoardToolbar filters={filters} columns={columns} members={members} onChange={setFilters} />
      {actionError && <ErrorText>{actionError}</ErrorText>}

      <div className="flex items-start gap-4">
        <div className="flex flex-1 items-start gap-4 overflow-x-auto pb-4">
          {columns.map((column) => (
            <ColumnView
              key={column.id}
              column={column}
              columns={columns}
              cards={cards.filter((c) => c.column_id === column.id)}
              members={members}
              onRename={(name) => rename(column, name)}
              onDelete={() => remove(column)}
              onAddCard={(title) => addCard(column, title)}
              onMoveCard={moveCard}
            />
          ))}
          <AddColumnForm onAdd={addColumn} />
        </div>
        {showMembers && (
          <MembersPanel boardId={boardId} members={members} isOwner={isOwner} onChange={refetch} />
        )}
      </div>
      {user && !isOwner && (
        <p className="text-xs text-zinc-500">You are a member of this board; only the owner manages members.</p>
      )}
    </div>
  );
}
