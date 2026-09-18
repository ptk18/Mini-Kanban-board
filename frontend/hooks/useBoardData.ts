"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { BoardDetail, Card, CardFilters, Member } from "@/lib/api";

export type BoardData = {
  board: BoardDetail | null;
  cards: Card[];
  members: Member[];
  error: string | null;
  loading: boolean;
  refetch: () => Promise<void>;
};

export function describeError(error: unknown): string {
  return error instanceof api.ApiError ? error.detail : "Could not reach the server";
}

/**
 * Board, cards (filtered) and members for one board. There are no live
 * updates (plan §5): callers `refetch()` after their own mutations, and the
 * hook refetches whenever the tab regains focus.
 */
export function useBoardData(boardId: number, filters: CardFilters): BoardData {
  const [board, setBoard] = useState<BoardDetail | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const filterKey = api.buildCardQuery(filters);

  const refetch = useCallback(
    () =>
      Promise.all([api.getBoard(boardId), api.listCards(boardId, filters), api.listMembers(boardId)])
        .then(([nextBoard, nextCards, nextMembers]) => {
          setBoard(nextBoard);
          setCards(nextCards);
          setMembers(nextMembers);
          setError(null);
        })
        .catch((e: unknown) => setError(describeError(e)))
        .finally(() => setLoading(false)),
    // filters is captured through its serialised form so a new object with
    // the same values does not refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [boardId, filterKey],
  );

  useEffect(() => {
    void refetch();
  }, [refetch]);

  useEffect(() => {
    const onFocus = () => void refetch();
    const onVisible = () => {
      if (document.visibilityState === "visible") void refetch();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refetch]);

  return { board, cards, members, error, loading, refetch };
}
