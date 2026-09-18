import Link from "next/link";
import { SignupForm } from "@/components/SignupForm";

export default function SignupPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Sign up</h1>
      <SignupForm />
      <p className="text-sm text-zinc-400">
        Already have an account?{" "}
        <Link href="/login" className="text-zinc-100 underline-offset-4 hover:underline">
          Log in
        </Link>
      </p>
    </main>
  );
}
