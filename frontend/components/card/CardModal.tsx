"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import type { Card, CardUpdate, Column, Label, Member, Priority } from "@/lib/api";
import { describeError } from "@/hooks/useBoardData";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { ChecklistSection } from "@/components/card/ChecklistSection";
import { CommentsSection } from "@/components/card/CommentsSection";
import { ErrorText, PrimaryButton, SecondaryButton, TextInput } from "@/components/ui";

const selectClass =
  "rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-300";
const textareaClass =
  "w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-300";

type Draft = {
  title: string;
  description: string;
  column_id: number;
  priority: Priority;
  due_date: string; // YYYY-MM-DD or ""
  assignee_id: number | null;
  label_ids: number[];
};

function toDraft(card: Card): Draft {
  return {
    title: card.title,
    description: card.description,
    column_id: card.column_id,
    priority: card.priority,
    due_date: card.due_date ? card.due_date.slice(0, 10) : "",
    assignee_id: card.assignee_id,
    label_ids: card.labels.map((l) => l.id),
  };
}

/** Only the fields that differ from the card, in the PATCH body's shape. */
export function diffCard(card: Card, draft: Draft): CardUpdate {
  const body: CardUpdate = {};
  const title = draft.title.trim();
  if (title !== card.title) body.title = title;
  if (draft.description !== card.description) body.description = draft.description;
  if (draft.column_id !== card.column_id) body.column_id = draft.column_id;
  if (draft.priority !== card.priority) body.priority = draft.priority;
  const due = draft.due_date ? `${draft.due_date}T00:00:00Z` : null;
  if ((card.due_date ? card.due_date.slice(0, 10) : "") !== draft.due_date) body.due_date = due;
  if (draft.assignee_id !== card.assignee_id) body.assignee_id = draft.assignee_id;
  const current = card.labels.map((l) => l.id).sort().join(",");
  if ([...draft.label_ids].sort().join(",") !== current) body.label_ids = draft.label_ids;
  return body;
}

export function CardModal({
  cardId,
  columns,
  members,
  cards,
  onClose,
  onChanged,
}: {
  cardId: number;
  columns: Column[];
  members: Member[];
  cards: Card[];
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const [card, setCard] = useState<Card | null>(null);
  const [labels, setLabels] = useState<Label[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [newLabel, setNewLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const fail = useCallback((e: unknown) => setError(describeError(e)), []);

  const reload = useCallback(
    () =>
      api
        .getCard(cardId)
        .then((next) => {
          setCard(next);
          setDraft((current) => current ?? toDraft(next));
        })
        .catch(fail),
    [cardId, fail],
  );

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!card) return;
    api.listLabels(card.board_id).then(setLabels).catch(fail);
  }, [card?.board_id, card, fail]);

  useFocusTrap(dialogRef, onClose);

  // The form mounts after the card loads; move focus from Close to the title.
  const loaded = card !== null;
  useEffect(() => {
    if (loaded) titleRef.current?.focus();
  }, [loaded]);

  const changed = () => reload().then(onChanged);

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    if (!card || !draft) return;
    if (!draft.title.trim()) {
      setError("Title is required");
      return;
    }
    const body = diffCard(card, draft);
    if (Object.keys(body).length === 0) {
      onClose();
      return;
    }
    setSaving(true);
    try {
      const updated = await api.updateCard(card.id, body);
      setCard(updated);
      setDraft(toDraft(updated));
      setError(null);
      await onChanged();
      onClose();
    } catch (e) {
      fail(e);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!card || !window.confirm(`Delete "${card.title}"? Its checklist and comments go with it.`)) return;
    try {
      await api.deleteCard(card.id);
      await onChanged();
      onClose();
    } catch (e) {
      fail(e);
    }
  }

  async function handleNewLabel() {
    if (!card || !draft) return;
    const name = newLabel.trim();
    if (!name) return;
    try {
      const label = await api.createLabel(card.board_id, name);
      setLabels((current) => [...current, label]);
      setDraft({ ...draft, label_ids: [...draft.label_ids, label.id] });
      setNewLabel("");
      setError(null);
    } catch (e) {
      fail(e);
    }
  }

  const parent = card?.parent_card_id != null ? cards.find((c) => c.id === card.parent_card_id) : undefined;
  const set = (patch: Partial<Draft>) => setDraft((d) => (d ? { ...d, ...patch } : d));

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 sm:p-8"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="card-modal-title"
        className="flex w-full max-w-2xl flex-col gap-6 rounded-lg border border-zinc-800 bg-zinc-900 p-6"
      >
        <div className="flex items-center gap-3">
          <h2 id="card-modal-title" className="text-lg font-semibold">
            {card ? card.title : "Loading…"}
          </h2>
          <SecondaryButton onClick={onClose} aria-label="Close" className="ml-auto">
            Close
          </SecondaryButton>
        </div>
        {error && <ErrorText>{error}</ErrorText>}

        {card && draft && (
          <>
            <form onSubmit={handleSave} className="flex flex-col gap-4">
              {parent && (
                <p className="text-xs text-zinc-400">
                  Child of <span className="text-zinc-200">{parent.title}</span>
                </p>
              )}
              <div className="flex flex-col gap-1 text-sm">
                <label htmlFor="card-title">Title</label>
                <TextInput id="card-title" ref={titleRef} value={draft.title} onChange={(e) => set({ title: e.target.value })} />
              </div>
              <div className="flex flex-col gap-1 text-sm">
                <label htmlFor="card-description">Description</label>
                <textarea
                  id="card-description"
                  rows={4}
                  value={draft.description}
                  onChange={(e) => set({ description: e.target.value })}
                  className={textareaClass}
                />
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="flex flex-col gap-1">
                  <label htmlFor="card-column">Column</label>
                  <select
                    id="card-column"
                    className={selectClass}
                    value={draft.column_id}
                    onChange={(e) => set({ column_id: Number(e.target.value) })}
                  >
                    {columns.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label htmlFor="card-priority">Priority</label>
                  <select
                    id="card-priority"
                    className={selectClass}
                    value={draft.priority}
                    onChange={(e) => set({ priority: e.target.value as Priority })}
                  >
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label htmlFor="card-due">Due date</label>
                  <TextInput
                    id="card-due"
                    type="date"
                    value={draft.due_date}
                    onChange={(e) => set({ due_date: e.target.value })}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label htmlFor="card-assignee">Assignee</label>
                  <select
                    id="card-assignee"
                    className={selectClass}
                    value={draft.assignee_id ?? ""}
                    onChange={(e) => set({ assignee_id: e.target.value ? Number(e.target.value) : null })}
                  >
                    <option value="">Unassigned</option>
                    {members.map((m) => (
                      <option key={m.user_id} value={m.user_id}>
                        {m.display_name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <fieldset className="flex flex-col gap-2 text-sm">
                <legend className="mb-1">Labels</legend>
                <div className="flex flex-wrap gap-3">
                  {labels.map((label) => (
                    <label key={label.id} className="flex items-center gap-1">
                      <input
                        type="checkbox"
                        checked={draft.label_ids.includes(label.id)}
                        onChange={(e) =>
                          set({
                            label_ids: e.target.checked
                              ? [...draft.label_ids, label.id]
                              : draft.label_ids.filter((id) => id !== label.id),
                          })
                        }
                        className="accent-zinc-100"
                      />
                      {label.name}
                    </label>
                  ))}
                  {labels.length === 0 && <span className="text-zinc-500">No labels yet.</span>}
                </div>
                <div className="flex gap-2">
                  <TextInput
                    aria-label="New label name"
                    placeholder="New label"
                    value={newLabel}
                    onChange={(e) => setNewLabel(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        void handleNewLabel();
                      }
                    }}
                    className="flex-1"
                  />
                  <SecondaryButton onClick={handleNewLabel}>Add label</SecondaryButton>
                </div>
              </fieldset>
              <div className="flex gap-2">
                <PrimaryButton type="submit" disabled={saving}>
                  {saving ? "Saving…" : "Save"}
                </PrimaryButton>
                <SecondaryButton onClick={handleDelete} className="ml-auto text-red-400">
                  Delete card
                </SecondaryButton>
              </div>
            </form>

            <ChecklistSection cardId={card.id} items={card.checklist_items} onChanged={changed} onError={fail} />
            <CommentsSection cardId={card.id} />
          </>
        )}
      </div>
    </div>
  );
}
