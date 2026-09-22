import { LANGUAGES } from "../utils/languages";
import type { Language } from "../types";

interface Props {
  value: Language;
  onChange: (language: Language) => void;
}

export function LanguageSelector({ value, onChange }: Props) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      Answer language
      <select
        className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2"
        value={value}
        onChange={(event) => onChange(event.target.value as Language)}
      >
        {LANGUAGES.map((item) => (
          <option key={item.id} value={item.id}>
            {item.label}
          </option>
        ))}
      </select>
    </label>
  );
}
