import Link from "next/link";
import { LoginForm } from "@/components/LoginForm";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Log in</h1>
      <LoginForm />
      <p className="text-sm text-zinc-400">
        No account?{" "}
        <Link href="/signup" className="text-zinc-100 underline-offset-4 hover:underline">
          Sign up
        </Link>
      </p>
    </main>
  );
}
