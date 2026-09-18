"use client";

import { useEffect, useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import type { Comment } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { describeError } from "@/hooks/useBoardData";
import { ErrorText, PrimaryButton, SecondaryButton } from "@/components/ui";

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

const textareaClass =
  "w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-300";

export function CommentsSection({ cardId }: { cardId: number }) {
  const { user } = useAuth();
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newContent, setNewContent] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");

  const load = () => api.listComments(cardId).then(setComments).catch((e) => setError(describeError(e)));

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cardId]);

  async function run(action: () => Promise<unknown>) {
    try {
      await action();
      setError(null);
      await load();
    } catch (e) {
      setError(describeError(e));
    }
  }

  async function handlePost(event: FormEvent) {
    event.preventDefault();
    const content = newContent.trim();
    if (!content) return;
    await run(() => api.createComment(cardId, content));
    setNewContent("");
  }

  async function commitEdit(comment: Comment) {
    const content = draft.trim();
    if (content && content !== comment.content) {
      await run(() => api.updateComment(comment.id, content));
    }
    setEditingId(null);
  }

  return (
    <section aria-labelledby="comments-heading" className="flex flex-col gap-2">
      <h3 id="comments-heading" className="text-sm font-medium uppercase tracking-wide text-zinc-400">
        Comments
      </h3>
      {error && <ErrorText>{error}</ErrorText>}
      {comments === null ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : comments.length === 0 ? (
        <p className="text-sm text-zinc-500">No comments yet.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {comments.map((comment) => {
            const own = user?.id === comment.author.id;
            const edited = comment.updated_at !== comment.created_at;
            return (
              <li key={comment.id} className="flex flex-col gap-1 text-sm">
                <div className="flex items-baseline gap-2 text-xs text-zinc-400">
                  <span className="font-medium text-zinc-200">{comment.author.display_name}</span>
                  <time dateTime={comment.created_at}>{formatTime(comment.created_at)}</time>
                  {edited && <span>(edited)</span>}
                  {own && editingId !== comment.id && (
                    <span className="ml-auto flex gap-1">
                      <SecondaryButton
                        aria-label="Edit comment"
                        className="px-2 py-0.5 text-xs"
                        onClick={() => {
                          setDraft(comment.content);
                          setEditingId(comment.id);
                        }}
                      >
                        Edit
                      </SecondaryButton>
                      <SecondaryButton
                        aria-label="Delete comment"
                        className="px-2 py-0.5 text-xs text-red-400"
                        onClick={() => {
                          if (window.confirm("Delete this comment?")) void run(() => api.deleteComment(comment.id));
                        }}
                      >
                        Delete
                      </SecondaryButton>
                    </span>
                  )}
                </div>
                {editingId === comment.id ? (
                  <div className="flex flex-col gap-1">
                    <textarea
                      aria-label="Edit comment text"
                      value={draft}
                      autoFocus
                      rows={2}
                      onChange={(e) => setDraft(e.target.value)}
                      className={textareaClass}
                    />
                    <div className="flex gap-2">
                      <PrimaryButton onClick={() => void commitEdit(comment)}>Save comment</PrimaryButton>
                      <SecondaryButton onClick={() => setEditingId(null)}>Cancel</SecondaryButton>
                    </div>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap leading-relaxed">{comment.content}</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <form onSubmit={handlePost} className="flex flex-col gap-2">
        <textarea
          aria-label="New comment"
          placeholder="Write a comment"
          rows={2}
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          className={textareaClass}
        />
        <PrimaryButton type="submit" className="self-start">
          Post comment
        </PrimaryButton>
      </form>
    </section>
  );
}
