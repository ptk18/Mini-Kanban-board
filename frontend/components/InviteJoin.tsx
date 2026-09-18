"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { describeError } from "@/hooks/useBoardData";
import { ErrorText } from "@/components/ui";

/**
 * Consumes an invite link: signed-in users join and land on the board;
 * everyone else goes to /login with this page as the return address.
 */
export function InviteJoin({ token }: { token: string }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace(`/login?next=${encodeURIComponent(`/invite/${token}`)}`);
      return;
    }
    let cancelled = false;
    api
      .joinByInvite(token)
      .then(({ board }) => {
        if (!cancelled) router.replace(`/boards/${board.id}`);
      })
      .catch((e) => {
        if (!cancelled) setError(describeError(e));
      });
    return () => {
      cancelled = true;
    };
  }, [loading, user, token, router]);

  if (error) return <ErrorText>{error}</ErrorText>;
  return <p className="text-sm text-zinc-500">Joining the board…</p>;
}
