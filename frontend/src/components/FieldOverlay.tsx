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
  const color = active
    ? "border-coral bg-coral/20 ring-2 ring-coral/30"
    : completed
      ? "border-leaf bg-leaf/15"
      : low
        ? "border-red-700 bg-red-500/10"
        : "border-leaf/70 bg-leaf/10 hover:bg-leaf/15";
  return (
    <button
      type="button"
      aria-label={field.label || field.id}
      className={`absolute border-2 transition ${color}`}
      style={overlayStyle(field.input_box)}
      onClick={() => onSelect(field.id)}
    />
  );
}
