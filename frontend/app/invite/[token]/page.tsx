"use client";

import { useParams } from "next/navigation";
import { InviteJoin } from "@/components/InviteJoin";

export default function InvitePage() {
  const params = useParams<{ token: string }>();
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Board invitation</h1>
      <InviteJoin token={params.token} />
    </main>
  );
}
