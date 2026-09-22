import type { DetectedField } from "../types";
import { validateAnswer } from "../utils/validation";

interface Props {
  field: DetectedField;
  value: string;
  onChange: (value: string) => void;
}

export function FieldInput({ field, value, onChange }: Props) {
  const error = validateAnswer(field, value);
  if (field.field_type === "signature") {
    return <p className="rounded bg-slate-100 p-3 text-sm">Sign the official paper by hand. FormSathi never creates a signature.</p>;
  }
  if (field.field_type === "checkbox" || field.field_type === "radio") {
    return (
      <label className="flex items-center gap-2">
        <input
          type={field.field_type}
          checked={value === "true"}
          onChange={(event) => onChange(event.target.checked ? "true" : "")}
        />
        {field.label || "Select this option"}
      </label>
    );
  }
  const Tag = field.field_type === "multiline" ? "textarea" : "input";
  return (
    <div>
      <label className="block text-sm font-medium" htmlFor={field.id}>
        Your answer
      </label>
      <Tag
        id={field.id}
        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? <p className="mt-1 text-sm text-red-800">{error}</p> : null}
    </div>
  );
}
