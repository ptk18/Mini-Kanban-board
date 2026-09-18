"use client";

import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import type { Board } from "@/lib/api";
import { ErrorText, PrimaryButton, SecondaryButton, TextInput } from "@/components/ui";

function describe(error: unknown): string {
  return error instanceof api.ApiError ? error.detail : "Could not reach the server";
}

export function BoardList() {
  const [boards, setBoards] = useState<Board[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api.listBoards().then(setBoards).catch((e) => setError(describe(e)));
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    const name = newName.trim();
    if (!name) {
      setError("Board name is required");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const created = await api.createBoard(name);
      setBoards((current) => [...(current ?? []), created]);
      setNewName("");
    } catch (e) {
      setError(describe(e));
    } finally {
      setCreating(false);
    }
  }

  async function handleRename(board: Board, name: string) {
    const updated = await api.renameBoard(board.id, name);
    setBoards((current) => current?.map((b) => (b.id === board.id ? updated : b)) ?? null);
  }

  async function handleDelete(board: Board) {
    if (!window.confirm(`Delete "${board.name}"? Its columns and cards go with it.`)) return;
    try {
      await api.deleteBoard(board.id);
      setBoards((current) => current?.filter((b) => b.id !== board.id) ?? null);
    } catch (e) {
      setError(describe(e));
    }
  }

  return (
    <section className="flex flex-col gap-6">
      <form onSubmit={handleCreate} className="flex items-center gap-2">
        <TextInput
          aria-label="New board name"
          placeholder="New board"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          className="flex-1"
        />
        <PrimaryButton type="submit" disabled={creating}>
          Create board
        </PrimaryButton>
      </form>
      {error && <ErrorText>{error}</ErrorText>}

      {boards === null ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : boards.length === 0 ? (
        <p className="text-sm text-zinc-500">No boards yet. Create one above.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {boards.map((board) => (
            <BoardRow
              key={board.id}
              board={board}
              onRename={(name) => handleRename(board, name)}
              onDelete={() => handleDelete(board)}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function BoardRow({
  board,
  onRename,
  onDelete,
}: {
  board: Board;
  onRename: (name: string) => Promise<void>;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(board.name);
  const [error, setError] = useState<string | null>(null);

  function startEditing() {
    setDraft(board.name);
    setError(null);
    setEditing(true);
  }

  async function commit() {
    const name = draft.trim();
    if (!name) {
      setError("Board name is required");
      return;
    }
    if (name !== board.name) {
      try {
        await onRename(name);
      } catch (e) {
        setError(describe(e));
        return;
      }
    }
    setEditing(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void commit();
    } else if (event.key === "Escape") {
      setEditing(false);
    }
  }

  return (
    <li className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3">
      {editing ? (
        <div className="flex flex-1 flex-col gap-1">
          <TextInput
            aria-label={`Rename ${board.name}`}
            value={draft}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={() => void commit()}
          />
          {error && <ErrorText>{error}</ErrorText>}
        </div>
      ) : (
        <Link href={`/boards/${board.id}`} className="flex-1 text-sm font-medium hover:underline">
          {board.name}
        </Link>
      )}
      <span className="text-xs uppercase tracking-wide text-zinc-500">{board.role}</span>
      {!editing && (
        <SecondaryButton onClick={startEditing} aria-label={`Rename ${board.name}`}>
          Rename
        </SecondaryButton>
      )}
      {board.role === "owner" && (
        <SecondaryButton
          onClick={onDelete}
          aria-label={`Delete ${board.name}`}
          className="text-red-400"
        >
          Delete
        </SecondaryButton>
      )}
    </li>
  );
}
