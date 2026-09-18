import type { InputHTMLAttributes } from "react";
import { ErrorText, TextInput } from "@/components/ui";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  id: string;
  label: string;
  error?: string;
};

/** A labelled input whose error is announced but kept out of the label text. */
export function Field({ id, label, error, ...input }: Props) {
  const errorId = `${id}-error`;
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      <TextInput
        id={id}
        {...input}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
      />
      {error && <ErrorText id={errorId}>{error}</ErrorText>}
    </div>
  );
}
