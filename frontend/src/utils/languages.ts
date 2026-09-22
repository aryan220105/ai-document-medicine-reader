import type { Language } from "../types";

export const LANGUAGES: { id: Language; label: string; locale: string }[] = [
  { id: "en", label: "English", locale: "en-IN" },
  { id: "hi", label: "Hindi", locale: "hi-IN" },
  { id: "kn", label: "Kannada", locale: "kn-IN" },
];

export function localeFor(language: Language): string {
  return LANGUAGES.find((item) => item.id === language)?.locale ?? "en-IN";
}
