"use client";

import { useState } from "react";
import * as api from "@/lib/api";
import type { AiBreakdown, AiEstimate, AiImprove, AiPrioritize, AiSummarize, Card, Priority, ProposedTask } from "@/lib/api";
import { describeError } from "@/hooks/useBoardData";
import { ErrorText, PrimaryButton, SecondaryButton, TextInput } from "@/components/ui";

type Preview =
  | { kind: "improve"; data: AiImprove }
  | { kind: "prioritize"; data: AiPrioritize }
  | { kind: "estimate"; data: AiEstimate }
  | { kind: "summarize"; data: AiSummarize }
  | { kind: "breakdown"; data: AiBreakdown };

type Kind = Preview["kind"];

const ACTIONS: { kind: Kind; label: string }[] = [
  { kind: "breakdown", label: "Break down" },
  { kind: "improve", label: "Improve" },
  { kind: "prioritize", label: "Prioritize" },
  { kind: "estimate", label: "Estimate effort" },
  { kind: "summarize", label: "Summarize" },
];

/** The line Approve appends to the description for an estimate; there is no
 * estimate field on a card (plan §13), so the description carries it. */
export function estimateLine(estimate: AiEstimate): string {
  return `Estimate: ${estimate.size} (${estimate.time_estimate})`;
}

const textareaClass =
  "w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-300";
const selectClass =
  "rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-300";

export function AiPanel({ card, onApplied }: { card: Card; onApplied: () => Promise<void> }) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState<Kind | "apply" | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Editable copies of the proposal; Approve sends these, not the raw reply.
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [tasks, setTasks] = useState<ProposedTask[]>([]);

  async function run(kind: Kind) {
    setBusy(kind);
    setError(null);
    try {
      switch (kind) {
        case "improve": {
          const data = await api.aiImprove(card.id);
          setTitle(data.title);
          setDescription(data.description);
          setPreview({ kind, data });
          break;
        }
        case "prioritize": {
          const data = await api.aiPrioritize(card.id);
          setPriority(data.priority);
          setPreview({ kind, data });
          break;
        }
        case "estimate":
          setPreview({ kind, data: await api.aiEstimate(card.id) });
          break;
        case "summarize":
          setPreview({ kind, data: await api.aiSummarize(card.id) });
          break;
        case "breakdown": {
          const data = await api.aiBreakdown(card.id);
          setTasks(data.tasks);
          setPreview({ kind, data });
          break;
        }
      }
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(null);
    }
  }

  async function approve() {
    if (!preview) return;
    setBusy("apply");
    setError(null);
    try {
      switch (preview.kind) {
        case "improve":
          await api.updateCard(card.id, { title: title.trim(), description });
          break;
        case "prioritize":
          await api.updateCard(card.id, { priority });
          break;
        case "estimate":
          await api.updateCard(card.id, {
            description: [card.description, estimateLine(preview.data)].filter(Boolean).join("\n\n"),
          });
          break;
        case "breakdown": {
          const cleaned = tasks
            .map((t) => ({ title: t.title.trim(), description: t.description }))
            .filter((t) => t.title);
          if (cleaned.length === 0) {
            setError("Keep at least one task");
            return;
          }
          await api.aiApplyBreakdown(card.id, cleaned);
          break;
        }
        case "summarize":
          return;
      }
      setPreview(null);
      await onApplied();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(null);
    }
  }

  function discard() {
    setPreview(null);
    setError(null);
  }

  return (
    <section aria-labelledby="ai-heading" className="flex flex-col gap-3">
      <h3 id="ai-heading" className="text-sm font-medium uppercase tracking-wide text-zinc-400">
        AI
      </h3>
      <div role="group" aria-label="AI actions" className="flex flex-wrap gap-2">
        {ACTIONS.map((action) => (
          <SecondaryButton
            key={action.kind}
            onClick={() => run(action.kind)}
            disabled={busy !== null}
            aria-busy={busy === action.kind}
          >
            {busy === action.kind ? `${action.label}…` : action.label}
          </SecondaryButton>
        ))}
      </div>
      {error && <ErrorText>{error}</ErrorText>}

      {preview && (
        <div
          role="region"
          aria-label="AI preview"
          className="flex flex-col gap-3 rounded-lg border border-zinc-800 bg-zinc-950 p-4 text-sm"
        >
          <p className="leading-relaxed text-zinc-300">{preview.data.text}</p>

          {preview.kind === "improve" && (
            <>
              <label className="flex flex-col gap-1">
                Proposed title
                <TextInput value={title} onChange={(e) => setTitle(e.target.value)} />
              </label>
              <label className="flex flex-col gap-1">
                Proposed description
                <textarea rows={4} value={description} onChange={(e) => setDescription(e.target.value)} className={textareaClass} />
              </label>
            </>
          )}

          {preview.kind === "prioritize" && (
            <label className="flex items-center gap-2">
              Proposed priority
              <select className={selectClass} value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </label>
          )}

          {preview.kind === "estimate" && (
            <p>
              <span className="font-medium">{preview.data.size}</span> · {preview.data.time_estimate}
              <span className="block text-xs text-zinc-500">Approve appends “{estimateLine(preview.data)}” to the description.</span>
            </p>
          )}

          {preview.kind === "breakdown" && (
            <ul className="flex flex-col gap-2">
              {tasks.map((task, index) => (
                <li key={index} className="flex flex-col gap-1 rounded-md border border-zinc-800 p-2">
                  <div className="flex gap-2">
                    <TextInput
                      aria-label={`Task ${index + 1} title`}
                      value={task.title}
                      onChange={(e) => setTasks(tasks.map((t, i) => (i === index ? { ...t, title: e.target.value } : t)))}
                      className="flex-1"
                    />
                    <SecondaryButton
                      aria-label={`Remove task ${index + 1}`}
                      onClick={() => setTasks(tasks.filter((_, i) => i !== index))}
                      className="px-2 text-red-400"
                    >
                      ×
                    </SecondaryButton>
                  </div>
                  <TextInput
                    aria-label={`Task ${index + 1} description`}
                    value={task.description}
                    onChange={(e) => setTasks(tasks.map((t, i) => (i === index ? { ...t, description: e.target.value } : t)))}
                  />
                </li>
              ))}
              <li>
                <SecondaryButton onClick={() => setTasks([...tasks, { title: "", description: "" }])}>Add task</SecondaryButton>
              </li>
            </ul>
          )}

          <div className="flex gap-2">
            {preview.kind !== "summarize" && (
              <PrimaryButton onClick={approve} disabled={busy !== null}>
                {busy === "apply" ? "Applying…" : "Approve"}
              </PrimaryButton>
            )}
            <SecondaryButton onClick={discard}>{preview.kind === "summarize" ? "Close" : "Discard"}</SecondaryButton>
          </div>
        </div>
      )}
    </section>
  );
}
