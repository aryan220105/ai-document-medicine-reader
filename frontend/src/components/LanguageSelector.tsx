import { useId } from "react";
import { EXPLANATION_LANGUAGE_HINT, EXPLANATION_LANGUAGE_LABEL, LANGUAGES } from "../utils/languages";
import type { Language } from "../types";

interface Props {
  value: Language;
  onChange: (language: Language) => void;
  /** Languages the current guidance bundle actually has text for. */
  available?: Language[];
  compact?: boolean;
}

export function LanguageSelector({ value, onChange, available, compact = false }: Props) {
  const ready = (language: Language) => !available || available.includes(language);
  // The switch appears more than once on the page (header and guidance panel), so each
  // instance needs its own id or the labels all point at the first select.
  const id = useId();
  const hintId = `${id}-hint`;

  return (
    <div className="text-sm">
      <label htmlFor={id} className="block font-medium text-slate-700">
        {EXPLANATION_LANGUAGE_LABEL}
      </label>
      <select
        id={id}
        aria-describedby={compact ? undefined : hintId}
        className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2"
        value={value}
        onChange={(event) => onChange(event.target.value as Language)}
      >
        {LANGUAGES.map((item) => (
          <option key={item.id} value={item.id}>
            {item.native === item.label ? item.label : `${item.native} — ${item.label}`}
            {ready(item.id) ? "" : " (not available for this field)"}
          </option>
        ))}
      </select>
      {compact ? null : (
        <p id={hintId} className="mt-1 text-xs text-slate-600">
          {EXPLANATION_LANGUAGE_HINT}
        </p>
      )}
    </div>
  );
}
