// Mirrors the backend rules in app/schemas/auth.py so the form can explain a
// problem before a round trip; the server remains the authority.
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PASSWORD_MIN_BYTES = 8;
const PASSWORD_MAX_BYTES = 72;

export function validateEmail(value: string): string | null {
  const email = value.trim().toLowerCase();
  if (!email) return "Email is required";
  if (!EMAIL_PATTERN.test(email)) return "Enter an email like name@example.com";
  return null;
}

export function validatePassword(value: string): string | null {
  const bytes = new TextEncoder().encode(value).length;
  if (bytes < PASSWORD_MIN_BYTES) return `Password must be at least ${PASSWORD_MIN_BYTES} characters`;
  if (bytes > PASSWORD_MAX_BYTES) return `Password must be at most ${PASSWORD_MAX_BYTES} bytes`;
  return null;
}

export function validateDisplayName(value: string): string | null {
  const name = value.trim();
  if (!name) return "Display name is required";
  if (name.length > 100) return "Display name must be at most 100 characters";
  return null;
}
