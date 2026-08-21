import type { Language } from "../types";

interface Props {
  value: Language;
  onChange: (language: Language) => void;
}

export function LanguageSelector({ value, onChange }: Props) {
  return (
    <label className="flex items-center gap-2 text-sm">
      Answer language
      <select
        aria-label="Answer language"
        className="rounded-full border border-sand bg-white px-3 py-2"
        value={value}
        onChange={(event) => onChange(event.target.value as Language)}
      >
        <option value="en">English</option>
        <option value="hi">Hindi</option>
        <option value="kn">Kannada</option>
      </select>
    </label>
  );
}
