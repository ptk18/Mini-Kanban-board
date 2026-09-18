"use client";

import { useState, type FormEvent } from "react";
import { ErrorText, PrimaryButton, TextInput } from "@/components/ui";

export function AddColumnForm({ onAdd }: { onAdd: (name: string) => Promise<void> }) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Column name is required");
      return;
    }
    try {
      await onAdd(trimmed);
      setName("");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add the column");
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex w-72 shrink-0 flex-col gap-2 rounded-lg border border-dashed border-zinc-800 p-3"
    >
      <TextInput
        aria-label="New column name"
        placeholder="Add column"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      {error && <ErrorText>{error}</ErrorText>}
      <PrimaryButton type="submit">Add column</PrimaryButton>
    </form>
  );
}
