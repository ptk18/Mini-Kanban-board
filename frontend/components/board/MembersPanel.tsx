"use client";

import { useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import type { Member } from "@/lib/api";
import { describeError } from "@/hooks/useBoardData";
import { ErrorText, PrimaryButton, SecondaryButton, TextInput } from "@/components/ui";

export function MembersPanel({
  boardId,
  members,
  isOwner,
  onChange,
}: {
  boardId: number;
  members: Member[];
  isOwner: boolean;
  onChange: () => Promise<void>;
}) {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function copyInviteLink() {
    try {
      const invite = await api.getInvite(boardId);
      const url = `${window.location.origin}${invite.invite_path}`;
      await navigator.clipboard.writeText(url);
      setMessage(`Invite link copied: ${url}`);
      setError(null);
    } catch (e) {
      setError(describeError(e));
    }
  }

  async function handleInvite(event: FormEvent) {
    event.preventDefault();
    const value = email.trim();
    if (!value) return;
    try {
      const member = await api.inviteByEmail(boardId, value);
      setMessage(`${member.display_name} is a member.`);
      setError(null);
      setEmail("");
      await onChange();
    } catch (e) {
      setError(describeError(e));
    }
  }

  async function handleRemove(member: Member) {
    if (!window.confirm(`Remove ${member.display_name} from this board?`)) return;
    try {
      await api.removeMember(boardId, member.user_id);
      setMessage(`${member.display_name} removed.`);
      setError(null);
      await onChange();
    } catch (e) {
      setError(describeError(e));
    }
  }

  return (
    <aside aria-label="Members" className="flex w-80 flex-col gap-4 rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-sm">
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-400">Members</h2>
      <ul className="flex flex-col gap-2">
        {members.map((member) => (
          <li key={member.user_id} className="flex items-center gap-2">
            <span className="flex-1 truncate">
              {member.display_name}
              <span className="ml-2 text-xs text-zinc-500">{member.email}</span>
            </span>
            <span className="text-xs uppercase tracking-wide text-zinc-500">{member.role}</span>
            {isOwner && member.role !== "owner" && (
              <SecondaryButton
                onClick={() => handleRemove(member)}
                aria-label={`Remove ${member.display_name}`}
                className="px-2 py-1 text-xs text-red-400"
              >
                Remove
              </SecondaryButton>
            )}
          </li>
        ))}
      </ul>
      {isOwner && (
        <>
          <SecondaryButton onClick={copyInviteLink}>Copy invite link</SecondaryButton>
          <form onSubmit={handleInvite} className="flex gap-2">
            <TextInput
              type="email"
              aria-label="Invite by email"
              placeholder="name@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex-1"
            />
            <PrimaryButton type="submit">Invite</PrimaryButton>
          </form>
        </>
      )}
      {message && <p className="text-xs text-zinc-400">{message}</p>}
      {error && <ErrorText>{error}</ErrorText>}
    </aside>
  );
}
