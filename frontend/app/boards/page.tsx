import { AppHeader } from "@/components/AppHeader";
import { BoardList } from "@/components/BoardList";
import { RequireAuth } from "@/components/RequireAuth";

export default function BoardsPage() {
  return (
    <RequireAuth>
      <AppHeader />
      <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 p-8">
        <h1 className="text-3xl font-semibold tracking-tight">Boards</h1>
        <BoardList />
      </main>
    </RequireAuth>
  );
}
