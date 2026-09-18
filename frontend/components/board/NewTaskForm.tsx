"use client";

import { useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import type { ProposedCard } from "@/lib/api";
import { describeError } from "@/hooks/useBoardData";
import { ErrorText, PrimaryButton, TextInput } from "@/components/ui";

/**
 * "New task from text": asks POST /ai/create-task for a proposal and hands it
 * to the card modal for review; the card is only created when the user
 * saves there, through the normal card POST.
 */
export function NewTaskForm({ boardId, onProposal }: { boardId: number; onProposal: (p: ProposedCard) => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const value = text.trim();
    if (!value) return;
    setBusy(true);
    setError(null);
    try {
      onProposal(await api.aiCreateTask(boardId, value));
      setText("");
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-1">
      <div className="flex gap-2">
        <TextInput
          aria-label="New task from text"
          placeholder="New task from text, e.g. “Fix the login redirect, urgent, by Friday”"
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="w-96 max-w-full"
        />
        <PrimaryButton type="submit" disabled={busy}>
          {busy ? "Thinking…" : "Propose"}
        </PrimaryButton>
      </div>
      {error && <ErrorText>{error}</ErrorText>}
    </form>
  );
}
