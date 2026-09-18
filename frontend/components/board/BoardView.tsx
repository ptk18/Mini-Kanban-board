"use client";

import { useState } from "react";
import Link from "next/link";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { SortableContext, horizontalListSortingStrategy, sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import * as api from "@/lib/api";
import type { Card, CardFilters, Column, ProposedCard } from "@/lib/api";
import { applyCardMove, applyColumnMove, computeCardDrop, computeColumnDrop } from "@/lib/positions";
import { asDropTarget, columnDragId, dragData } from "@/components/board/dnd";
import { useAuth } from "@/lib/auth";
import { describeError, useBoardData } from "@/hooks/useBoardData";
import { AddColumnForm } from "@/components/board/AddColumnForm";
import { BoardToolbar } from "@/components/board/BoardToolbar";
import { ColumnView } from "@/components/board/ColumnView";
import { MembersPanel } from "@/components/board/MembersPanel";
import { NewTaskForm } from "@/components/board/NewTaskForm";
import { CardModal } from "@/components/card/CardModal";
import { ErrorText, SecondaryButton } from "@/components/ui";

export function BoardView({ boardId }: { boardId: number }) {
  const { user } = useAuth();
  const [filters, setFilters] = useState<CardFilters>({});
  const [showMembers, setShowMembers] = useState(false);
  const [openCardId, setOpenCardId] = useState<number | null>(null);
  const [proposal, setProposal] = useState<ProposedCard | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  // Drag-and-drop shows the new order immediately; cleared once the server
  // confirms (refetch) or when the request fails (rollback).
  const [optimistic, setOptimistic] = useState<{ cards?: Card[]; columns?: Column[] } | null>(null);
  const data = useBoardData(boardId, filters);
  const { board, members, error, loading, refetch } = data;
  const sensors = useSensors(
    // A small distance keeps clicks on the header, select and inputs working.
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  if (error) return <ErrorText>{error}</ErrorText>;
  if (loading || !board) return <p className="text-sm text-zinc-500">Loading…</p>;

  const cards = optimistic?.cards ?? data.cards;
  const columns = [...(optimistic?.columns ?? board.columns)].sort((a, b) => a.position - b.position);
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

  async function handleDragEnd({ active, over }: DragEndEvent) {
    const dragged = dragData(active);
    const target = asDropTarget(over);
    if (!dragged || !target) return;

    if (dragged.type === "column") {
      if (target.type !== "column") return;
      const position = computeColumnDrop(columns, dragged.id, target.id);
      if (position === null) return;
      setOptimistic({ columns: applyColumnMove(columns, dragged.id, position) });
      await settle(api.updateColumn(dragged.id, { position }));
      return;
    }

    const move = computeCardDrop(cards, dragged.id, target);
    if (!move) return;
    setOptimistic({ cards: applyCardMove(cards, dragged.id, move) });
    await settle(api.updateCard(dragged.id, move));
  }

  async function settle(request: Promise<unknown>) {
    try {
      await request;
      setActionError(null);
      await refetch();
    } catch (e) {
      setActionError(describeError(e));
    } finally {
      setOptimistic(null);
    }
  }

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
      <NewTaskForm boardId={boardId} onProposal={setProposal} />
      {actionError && <ErrorText>{actionError}</ErrorText>}

      <div className="flex items-start gap-4">
        <DndContext sensors={sensors} collisionDetection={closestCorners} onDragEnd={handleDragEnd}>
          <div className="flex flex-1 items-start gap-4 overflow-x-auto pb-4">
            <SortableContext items={columns.map((c) => columnDragId(c.id))} strategy={horizontalListSortingStrategy}>
              {columns.map((column) => (
                <ColumnView
                  key={column.id}
                  column={column}
                  columns={columns}
                  cards={cards
                    .filter((c) => c.column_id === column.id)
                    .sort((a, b) => a.position - b.position)}
                  members={members}
                  onRename={(name) => rename(column, name)}
                  onDelete={() => remove(column)}
                  onAddCard={(title) => addCard(column, title)}
                  onMoveCard={moveCard}
                  onOpenCard={(card) => setOpenCardId(card.id)}
                />
              ))}
            </SortableContext>
            <AddColumnForm onAdd={addColumn} />
          </div>
        </DndContext>
        {showMembers && (
          <MembersPanel boardId={boardId} members={members} isOwner={isOwner} onChange={refetch} />
        )}
      </div>
      {openCardId !== null && (
        <CardModal
          cardId={openCardId}
          boardId={boardId}
          columns={columns}
          members={members}
          cards={cards}
          onClose={() => setOpenCardId(null)}
          onChanged={refetch}
        />
      )}
      {proposal && (
        <CardModal
          cardId={null}
          boardId={boardId}
          proposal={proposal}
          columns={columns}
          members={members}
          cards={cards}
          onClose={() => setProposal(null)}
          onChanged={refetch}
        />
      )}
      {user && !isOwner && (
        <p className="text-xs text-zinc-500">You are a member of this board; only the owner manages members.</p>
      )}
    </div>
  );
}
