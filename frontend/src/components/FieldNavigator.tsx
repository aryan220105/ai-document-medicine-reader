import type { DetectedField } from "../types";

interface Props {
  fields: DetectedField[];
  selectedId: string | null;
  excluded: Set<string>;
  onSelect: (id: string) => void;
  onExclude: (id: string) => void;
  answers?: Record<string, string>;
}

/** What to call a field in the list. */
export function fieldTitle(field: DetectedField): string {
  // `display_label` is the disambiguated name the page interpreter worked out, which is
  // what stops two side-by-side "Name:" cells reading identically here.
  return field.display_label?.trim() || field.label?.trim() || field.id;
}

export function FieldNavigator({ fields, selectedId, excluded, onSelect, onExclude, answers = {} }: Props) {
  const pages = [...new Set(fields.map((field) => field.page_index))].sort((a, b) => a - b);
  const answered = fields.filter((field) => Boolean(answers[field.id])).length;

  return (
    <div className="space-y-4" data-testid="field-navigator">
      <div className="rounded-2xl bg-mist px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-leaf">Your checklist</p>
        <p className="mt-1 text-sm text-pine">
          {answered} of {fields.length} answered
        </p>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white">
          <div
            className="h-full rounded-full bg-leaf transition-all"
            style={{ width: `${fields.length ? (answered / fields.length) * 100 : 0}%` }}
          />
        </div>
      </div>
      {pages.map((page) => (
        <div key={page}>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-pine/70">Page {page + 1}</p>
          <ul className="space-y-2">
            {fields
              .filter((field) => field.page_index === page)
              .map((field, index) => {
                const office = field.filled_by === "office";
                const done = Boolean(answers[field.id]);
                const active = selectedId === field.id;
                return (
                  <li key={field.id}>
                    <button
                      type="button"
                      dir="auto"
                      className={`w-full rounded-xl border px-3 py-2.5 text-left transition ${
                        active
                          ? "border-coral/50 bg-coral/10 shadow-sm"
                          : done
                            ? "border-leaf/30 bg-leaf/5"
                            : "border-softline bg-white hover:border-leaf/35"
                      } ${office ? "opacity-70" : ""}`}
                      onClick={() => onSelect(field.id)}
                    >
                      <span className="flex items-start gap-2">
                        <span
                          className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[10px] font-bold ${
                            done ? "bg-leaf text-white" : active ? "bg-coral text-white" : "bg-mist text-pine"
                          }`}
                        >
                          {done ? "✓" : index + 1}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block font-medium text-ink">{fieldTitle(field)}</span>
                          <span className="text-xs uppercase tracking-wide text-pine/70">{field.field_type}</span>
                          {office ? (
                            <span
                              className="ml-2 rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-700"
                              data-testid="office-badge"
                            >
                              Office use
                            </span>
                          ) : null}
                          {field.confidence < 0.55 ? (
                            <span className="ml-2 text-xs text-red-800">Low confidence</span>
                          ) : null}
                        </span>
                      </span>
                    </button>
                    {field.confidence < 0.55 ? (
                      <button type="button" className="mt-1 text-xs text-leaf underline" onClick={() => onExclude(field.id)}>
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
