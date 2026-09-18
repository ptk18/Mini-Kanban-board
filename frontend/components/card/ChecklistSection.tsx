"use client";

import { useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import type { ChecklistItem } from "@/lib/api";
import { PrimaryButton, SecondaryButton, TextInput } from "@/components/ui";

const smallButton = "px-2 py-1 text-xs";

export function ChecklistSection({
  cardId,
  items,
  onChanged,
  onError,
}: {
  cardId: number;
  items: ChecklistItem[];
  onChanged: () => Promise<void>;
  onError: (error: unknown) => void;
}) {
  const [newContent, setNewContent] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const ordered = [...items].sort((a, b) => a.position - b.position);
  const done = ordered.filter((i) => i.completed).length;

  async function run(action: () => Promise<unknown>) {
    try {
      await action();
      await onChanged();
    } catch (e) {
      onError(e);
    }
  }

  async function handleAdd(event: FormEvent) {
    event.preventDefault();
    const content = newContent.trim();
    if (!content) return;
    await run(() => api.createChecklistItem(cardId, content));
    setNewContent("");
  }

  async function commitEdit(item: ChecklistItem) {
    const content = draft.trim();
    if (content && content !== item.content) {
      await run(() => api.updateChecklistItem(item.id, { content }));
    }
    setEditingId(null);
  }

  return (
    <section aria-labelledby="checklist-heading" className="flex flex-col gap-2">
      <h3 id="checklist-heading" className="text-sm font-medium uppercase tracking-wide text-zinc-400">
        Checklist{" "}
        <span className="normal-case tracking-normal text-zinc-500" data-testid="checklist-count">
          {done}/{ordered.length} done
        </span>
      </h3>
      <ul className="flex flex-col gap-1">
        {ordered.map((item, index) => (
          <li key={item.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              aria-label={`Toggle ${item.content}`}
              checked={item.completed}
              onChange={() => run(() => api.updateChecklistItem(item.id, { completed: !item.completed }))}
              className="accent-zinc-100"
            />
            {editingId === item.id ? (
              <TextInput
                aria-label={`Edit ${item.content}`}
                value={draft}
                autoFocus
                onChange={(e) => setDraft(e.target.value)}
                onBlur={() => void commitEdit(item)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void commitEdit(item);
                  } else if (e.key === "Escape") {
                    e.stopPropagation();
                    setEditingId(null);
                  }
                }}
                className="flex-1"
              />
            ) : (
              <button
                type="button"
                onClick={() => {
                  setDraft(item.content);
                  setEditingId(item.id);
                }}
                title="Click to edit"
                className={`flex-1 text-left ${item.completed ? "text-zinc-500 line-through" : ""}`}
              >
                {item.content}
              </button>
            )}
            <SecondaryButton
              aria-label={`Move ${item.content} up`}
              disabled={index === 0}
              onClick={() => run(() => api.updateChecklistItem(item.id, { position: index - 1 }))}
              className={smallButton}
            >
              ↑
            </SecondaryButton>
            <SecondaryButton
              aria-label={`Move ${item.content} down`}
              disabled={index === ordered.length - 1}
              onClick={() => run(() => api.updateChecklistItem(item.id, { position: index + 1 }))}
              className={smallButton}
            >
              ↓
            </SecondaryButton>
            <SecondaryButton
              aria-label={`Remove ${item.content}`}
              onClick={() => run(() => api.deleteChecklistItem(item.id))}
              className={`${smallButton} text-red-400`}
            >
              ×
            </SecondaryButton>
          </li>
        ))}
      </ul>
      <form onSubmit={handleAdd} className="flex gap-2">
        <TextInput
          aria-label="New checklist item"
          placeholder="Add an item"
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          className="flex-1"
        />
        <PrimaryButton type="submit">Add item</PrimaryButton>
      </form>
    </section>
  );
}
