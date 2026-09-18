"use client";

import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { validateEmail, validatePassword } from "@/lib/validation";
import { Field } from "@/components/Field";
import { ErrorText, PrimaryButton } from "@/components/ui";

export function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get("next");
  // Only follow in-app paths so a crafted link cannot send users elsewhere.
  const destination = next && next.startsWith("/") && !next.startsWith("//") ? next : "/boards";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: string }>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const next = {
      email: validateEmail(email) ?? undefined,
      password: validatePassword(password) ?? undefined,
    };
    setErrors(next);
    if (next.email || next.password) return;

    setSubmitting(true);
    try {
      await login(email, password);
      router.push(destination);
    } catch (error) {
      setErrors({
        form: error instanceof ApiError ? error.detail : "Could not reach the server",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex w-full max-w-sm flex-col gap-4">
      <Field
        id="login-email"
        label="Email"
        type="email"
        name="email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={errors.email}
      />
      <Field
        id="login-password"
        label="Password"
        type="password"
        name="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={errors.password}
      />
      {errors.form && <ErrorText>{errors.form}</ErrorText>}
      <PrimaryButton type="submit" disabled={submitting}>
        {submitting ? "Logging in…" : "Log in"}
      </PrimaryButton>
    </form>
  );
}
