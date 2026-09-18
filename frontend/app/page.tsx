import Link from "next/link";

export default function Page() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Mini Kanban</h1>
      <p className="text-sm text-zinc-400">A minimal Kanban board.</p>
      <nav className="mt-4 flex gap-4 text-sm">
        <Link href="/login" className="underline-offset-4 hover:underline">
          Log in
        </Link>
        <Link href="/signup" className="underline-offset-4 hover:underline">
          Sign up
        </Link>
        <Link href="/boards" className="underline-offset-4 hover:underline">
          Your boards
        </Link>
      </nav>
    </main>
  );
}
