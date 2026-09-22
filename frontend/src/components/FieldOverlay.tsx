import { overlayStyle } from "../utils/validation";
import type { DetectedField } from "../types";

interface Props {
  field: DetectedField;
  active: boolean;
  completed: boolean;
  onSelect: (id: string) => void;
}

export function FieldOverlay({ field, active, completed, onSelect }: Props) {
  const low = field.confidence < 0.55;
  const color = active ? "border-amber-500 bg-amber-300/25" : completed ? "border-teal-700 bg-teal-600/15" : low ? "border-red-700 bg-red-500/10" : "border-sky-700 bg-sky-500/10";
  return (
    <button
      type="button"
      aria-label={field.label || field.id}
      className={`absolute border-2 ${color}`}
      style={overlayStyle(field.input_box)}
      onClick={() => onSelect(field.id)}
    />
  );
}
