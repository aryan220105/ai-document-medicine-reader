import type { DetectedField } from "../types";
import { validateAnswer } from "../utils/validation";

interface Props {
  field: DetectedField;
  value: string;
  onChange: (value: string) => void;
}

export function FieldInput({ field, value }: Props) {
  const error = validateAnswer(field, value);
  const rule = field.validation_rule ?? null;

  if (field.field_type === "signature") {
    return (
      <p className="rounded-xl bg-mist p-3 text-sm text-ink">
        Sign the official paper by hand. FormSathi never creates a signature.
      </p>
    );
  }

  if (field.filled_by === "office" || rule?.kind === "office_use") {
    return <p className="rounded-xl bg-mist p-3 text-sm text-ink">This space is filled in by the office. Leave it blank.</p>;
  }

  if (field.field_type === "checkbox" || field.field_type === "radio") {
    return <p className="text-sm text-ink">Tick this box on the form.</p>;
  }

  return (
    <div>
      <p className="text-sm text-ink">Type in the box on the form. The letters appear there as you type.</p>
      {rule?.format && !error ? <p className="mt-1 text-xs text-pine/75">Format: {rule.format}</p> : null}
      {error ? (
        <p id={`${field.id}-error`} className="mt-1 text-sm text-red-800" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
