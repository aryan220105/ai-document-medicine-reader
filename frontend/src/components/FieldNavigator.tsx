import type { DetectedField } from "../types";

interface Props {
  fields: DetectedField[];
  selectedId: string | null;
  excluded: Set<string>;
  onSelect: (id: string) => void;
  onExclude: (id: string) => void;
}

/** What to call a field in the list. */
export function fieldTitle(field: DetectedField): string {
  // `display_label` is the disambiguated name the page interpreter worked out, which is
  // what stops two side-by-side "Name:" cells reading identically here.
  return field.display_label?.trim() || field.label?.trim() || field.id;
}

export function FieldNavigator({ fields, selectedId, excluded, onSelect, onExclude }: Props) {
  const pages = [...new Set(fields.map((field) => field.page_index))].sort((a, b) => a - b);
  return (
    <div className="space-y-4" data-testid="field-navigator">
      {pages.map((page) => (
        <div key={page}>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Page {page + 1}</p>
          <ul className="space-y-2">
            {fields
              .filter((field) => field.page_index === page)
              .map((field) => {
                const office = field.filled_by === "office";
                return (
                  <li key={field.id}>
                    <button
                      type="button"
                      dir="auto"
                      className={`w-full rounded-lg border px-3 py-2 text-left ${
                        selectedId === field.id ? "border-amber-500 bg-amber-50" : "border-slate-200 bg-white"
                      } ${office ? "opacity-70" : ""}`}
                      onClick={() => onSelect(field.id)}
                    >
                      <span className="block font-medium">{fieldTitle(field)}</span>
                      <span className="text-xs uppercase text-slate-500">{field.field_type}</span>
                      {office ? (
                        <span className="ml-2 rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-700" data-testid="office-badge">
                          Office use
                        </span>
                      ) : null}
                      {field.confidence < 0.55 ? <span className="ml-2 text-xs text-red-800">Low confidence</span> : null}
                    </button>
                    {field.confidence < 0.55 ? (
                      <button type="button" className="mt-1 text-xs underline" onClick={() => onExclude(field.id)}>
                        {excluded.has(field.id) ? "Include again" : "Exclude from guided steps"}
                      </button>
                    ) : null}
                  </li>
                );
              })}
          </ul>
        </div>
      ))}
    </div>
  );
}
