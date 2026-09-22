import type { DetectedField } from "../types";

interface Props {
  fields: DetectedField[];
  selectedId: string | null;
  excluded: Set<string>;
  onSelect: (id: string) => void;
  onExclude: (id: string) => void;
}

export function FieldNavigator({ fields, selectedId, excluded, onSelect, onExclude }: Props) {
  return (
    <ul className="space-y-2" data-testid="field-navigator">
      {fields.map((field) => (
        <li key={field.id}>
          <button
            type="button"
            className={`w-full rounded border px-3 py-2 text-left ${selectedId === field.id ? "border-amber-500 bg-amber-50" : "border-slate-200 bg-white"}`}
            onClick={() => onSelect(field.id)}
          >
            <span className="block font-medium">{field.label || field.id}</span>
            <span className="text-xs uppercase text-slate-500">{field.field_type}</span>
            {field.confidence < 0.55 ? <span className="ml-2 text-xs text-red-800">Low confidence</span> : null}
          </button>
          {field.confidence < 0.55 ? (
            <button type="button" className="mt-1 text-xs underline" onClick={() => onExclude(field.id)}>
              {excluded.has(field.id) ? "Include again" : "Exclude from guided steps"}
            </button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
