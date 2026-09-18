"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { validateDisplayName, validateEmail, validatePassword } from "@/lib/validation";
import { Field } from "@/components/Field";
import { ErrorText, PrimaryButton } from "@/components/ui";

type Errors = { email?: string; password?: string; displayName?: string; form?: string };

export function SignupForm() {
  const { signup } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const next: Errors = {
      email: validateEmail(email) ?? undefined,
      password: validatePassword(password) ?? undefined,
      displayName: validateDisplayName(displayName) ?? undefined,
    };
    setErrors(next);
    if (next.email || next.password || next.displayName) return;

    setSubmitting(true);
    try {
      await signup(email, password, displayName);
      router.push("/boards");
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
        id="signup-display-name"
        label="Display name"
        type="text"
        name="display_name"
        autoComplete="name"
        value={displayName}
        onChange={(e) => setDisplayName(e.target.value)}
        error={errors.displayName}
      />
      <Field
        id="signup-email"
        label="Email"
        type="email"
        name="email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={errors.email}
      />
      <Field
        id="signup-password"
        label="Password"
        type="password"
        name="password"
        autoComplete="new-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={errors.password}
      />
      {errors.form && <ErrorText>{errors.form}</ErrorText>}
      <PrimaryButton type="submit" disabled={submitting}>
        {submitting ? "Creating account…" : "Sign up"}
      </PrimaryButton>
    </form>
  );
}
