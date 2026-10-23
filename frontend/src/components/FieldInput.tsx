import type { DetectedField } from "../types";
import { validateAnswer } from "../utils/validation";

interface Props {
  field: DetectedField;
  value: string;
  onChange: (value: string) => void;
}

/** Rule kinds whose answers are numeric, so a numeric keypad is offered on a phone. */
const NUMERIC_KINDS = new Set([
  "integer",
  "decimal",
  "amount",
  "year",
  "mobile_in",
  "phone",
  "pincode_in",
  "aadhaar_in",
  "bank_account",
]);

export function FieldInput({ field, value, onChange }: Props) {
  const error = validateAnswer(field, value);
  const rule = field.validation_rule ?? null;

  if (field.field_type === "signature") {
    return (
      <p className="rounded bg-slate-100 p-3 text-sm">
        Sign the official paper by hand. FormSathi never creates a signature.
      </p>
    );
  }

  if (field.filled_by === "office" || rule?.kind === "office_use") {
    return (
      <p className="rounded bg-slate-100 p-3 text-sm">
        This space is filled in by the office. Leave it blank.
      </p>
    );
  }

  if (field.field_type === "checkbox" || field.field_type === "radio") {
    return (
      <label className="flex items-center gap-2">
        <input
          type={field.field_type}
          checked={value === "true"}
          onChange={(event) => onChange(event.target.checked ? "true" : "")}
        />
        {field.options[0]?.label || field.label || "Select this option"}
      </label>
    );
  }

  const multiline = field.field_type === "multiline";
  const Tag = multiline ? "textarea" : "input";
  const numeric = rule ? NUMERIC_KINDS.has(rule.kind) : false;

  return (
    <div>
      <label className="block text-sm font-medium" htmlFor={field.id}>
        Your answer
      </label>
      <Tag
        id={field.id}
        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
        value={value}
        rows={multiline ? 3 : undefined}
        /* The answer is the user's own, in whatever script they write it, so the browser
           decides direction from what they type rather than from the interface language. */
        dir="auto"
        inputMode={numeric && !multiline ? "numeric" : undefined}
        maxLength={rule?.max_length ?? undefined}
        placeholder={rule?.format ?? undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${field.id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {rule?.format && !error ? <p className="mt-1 text-xs text-slate-600">Format: {rule.format}</p> : null}
      {error ? (
        <p id={`${field.id}-error`} className="mt-1 text-sm text-red-800">
          {error}
        </p>
      ) : null}
    </div>
  );
}
