"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";
import type { Card, Column, Member } from "@/lib/api";
import { CardItem } from "@/components/board/CardItem";
import { ErrorText, PrimaryButton, SecondaryButton, TextInput } from "@/components/ui";

export function deleteColumnMessage(column: Column, cardCount: number): string {
  const cards = cardCount === 1 ? "1 card" : `${cardCount} cards`;
  return cardCount === 0
    ? `Delete the empty column "${column.name}"? Nothing else changes.`
    : `"${column.name}" still holds ${cards}. Columns are only deleted when empty — the cards stay where they are and the server will refuse. Move them first, then try again. Attempt anyway?`;
}

export function ColumnView({
  column,
  columns,
  cards,
  members,
  onRename,
  onDelete,
  onAddCard,
  onMoveCard,
}: {
  column: Column;
  columns: Column[];
  cards: Card[];
  members: Member[];
  onRename: (name: string) => Promise<void>;
  onDelete: () => Promise<void>;
  onAddCard: (title: string) => Promise<void>;
  onMoveCard: (card: Card, columnId: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(column.name);
  const [newTitle, setNewTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  function startEditing() {
    setDraft(column.name);
    setError(null);
    setEditing(true);
  }

  async function commitRename() {
    const name = draft.trim();
    if (!name) {
      setError("Column name is required");
      return;
    }
    if (name !== column.name) {
      try {
        await onRename(name);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Rename failed");
        return;
      }
    }
    setEditing(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void commitRename();
    } else if (event.key === "Escape") {
      setEditing(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm(deleteColumnMessage(column, cards.length))) return;
    try {
      await onDelete();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  async function handleAddCard(event: FormEvent) {
    event.preventDefault();
    const title = newTitle.trim();
    if (!title) return;
    try {
      await onAddCard(title);
      setNewTitle("");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add the card");
    }
  }

  return (
    <section
      aria-label={column.name}
      className="flex w-72 shrink-0 flex-col gap-2 rounded-lg bg-zinc-900 p-3"
    >
      <header className="flex items-center gap-2">
        {editing ? (
          <TextInput
            aria-label={`Rename ${column.name}`}
            value={draft}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={() => void commitRename()}
            className="flex-1"
          />
        ) : (
          <button
            type="button"
            onClick={startEditing}
            title="Click to rename"
            className="flex-1 truncate text-left text-sm font-medium uppercase tracking-wide text-zinc-400 hover:text-zinc-200"
          >
            {column.name}
            <span className="ml-2 text-xs normal-case tracking-normal text-zinc-500">{cards.length}</span>
          </button>
        )}
        <SecondaryButton
          onClick={handleDelete}
          aria-label={`Delete ${column.name}`}
          className="px-2 py-1 text-xs text-red-400"
        >
          Delete
        </SecondaryButton>
      </header>
      {error && <ErrorText>{error}</ErrorText>}

      <ul className="flex flex-col gap-2">
        {cards.map((card) => (
          <CardItem
            key={card.id}
            card={card}
            columns={columns}
            members={members}
            onMove={(columnId) => onMoveCard(card, columnId)}
          />
        ))}
      </ul>

      <form onSubmit={handleAddCard} className="mt-1 flex gap-2">
        <TextInput
          aria-label={`Add card to ${column.name}`}
          placeholder="Add card"
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          className="flex-1"
        />
        <PrimaryButton type="submit" className="px-2">
          Add
        </PrimaryButton>
      </form>
    </section>
  );
}
