import { useEffect, useRef } from "react";
import { overlayStyle, validateAnswer } from "../utils/validation";
import type { DetectedField } from "../types";

interface Props {
  field: DetectedField;
  active: boolean;
  completed: boolean;
  value: string;
  onSelect: (id: string) => void;
  onChange: (id: string, value: string) => void;
}

function canType(field: DetectedField): boolean {
  if (field.field_type === "signature" || field.field_type === "checkbox" || field.field_type === "radio") {
    return false;
  }
  if (field.filled_by === "office" || field.validation_rule?.kind === "office_use") {
    return false;
  }
  return true;
}

export function FieldOverlay({ field, active, completed, value, onSelect, onChange }: Props) {
  const low = field.confidence < 0.55;
  const typing = canType(field);
  const choice = field.field_type === "checkbox" || field.field_type === "radio";
  const inputRef = useRef<HTMLInputElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const error = typing ? validateAnswer(field, value) : null;
  const color = active
    ? "border-coral bg-coral/15 ring-2 ring-coral/30"
    : completed
      ? "border-leaf bg-leaf/10"
      : low
        ? "border-red-700 bg-red-500/10"
        : "border-leaf/70 bg-leaf/10 hover:bg-leaf/15";

  useEffect(() => {
    if (active && typing) {
      (inputRef.current ?? areaRef.current)?.focus();
    }
  }, [active, typing, field.id]);

  const label = field.label || field.id;

  return (
    <div className={`field-ink absolute border-2 transition ${color}`} style={overlayStyle(field.input_box)}>
      {typing && active ? (
        field.field_type === "multiline" ? (
          <textarea
            ref={areaRef}
            aria-label={label}
            className="field-ink-input"
            value={value}
            dir="auto"
            rows={2}
            aria-invalid={error ? true : undefined}
            onChange={(event) => onChange(field.id, event.target.value)}
          />
        ) : (
          <input
            ref={inputRef}
            aria-label={label}
            className="field-ink-input"
            value={value}
            dir="auto"
            aria-invalid={error ? true : undefined}
            onChange={(event) => onChange(field.id, event.target.value)}
          />
        )
      ) : (
        <button
          type="button"
          aria-label={label}
          aria-pressed={choice ? value === "true" : undefined}
          className="field-ink-button"
          onClick={() => {
            onSelect(field.id);
            if (choice && field.filled_by !== "office") {
              onChange(field.id, value === "true" ? "" : "true");
            }
          }}
        >
          {choice ? (value === "true" ? "✓" : "") : value}
        </button>
      )}
    </div>
  );
}
