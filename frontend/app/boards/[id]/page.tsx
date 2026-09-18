"use client";

import { useParams } from "next/navigation";
import { AppHeader } from "@/components/AppHeader";
import { BoardView } from "@/components/board/BoardView";
import { RequireAuth } from "@/components/RequireAuth";
import { ErrorText } from "@/components/ui";

export default function BoardPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  return (
    <RequireAuth>
      <AppHeader />
      <main className="flex flex-col gap-6 p-8">
        {Number.isInteger(id) ? <BoardView boardId={id} /> : <ErrorText>Not found</ErrorText>}
      </main>
    </RequireAuth>
  );
}
