"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export function AppHeader() {
  const { user, logout } = useAuth();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className="flex items-center justify-between border-b border-zinc-800 px-8 py-3">
      <Link href="/boards" className="text-sm font-semibold tracking-tight">
        Mini Kanban
      </Link>
      <div className="flex items-center gap-4 text-sm">
        {user && <span className="text-zinc-400">{user.display_name}</span>}
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-md bg-zinc-800 px-3 py-1.5 font-medium text-zinc-100 transition-colors hover:bg-zinc-700 focus-visible:ring-2 focus-visible:ring-zinc-300"
        >
          Log out
        </button>
      </div>
    </header>
  );
}
