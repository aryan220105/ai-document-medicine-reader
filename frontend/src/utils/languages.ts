import type { Language, TextDirection } from "../types";

export interface LanguageInfo {
  id: Language;
  label: string;
  /** The language's own name, so a reader who cannot read English can still find it. */
  native: string;
  locale: string;
  direction: TextDirection;
}

export const LANGUAGES: LanguageInfo[] = [
  { id: "en", label: "English", native: "English", locale: "en-IN", direction: "ltr" },
  { id: "hi", label: "Hindi", native: "हिन्दी", locale: "hi-IN", direction: "ltr" },
  { id: "kn", label: "Kannada", native: "ಕನ್ನಡ", locale: "kn-IN", direction: "ltr" },
  { id: "ur", label: "Urdu", native: "اردو", locale: "ur-IN", direction: "rtl" },
];

export const LANGUAGE_IDS: Language[] = LANGUAGES.map((item) => item.id);

export function localeFor(language: Language): string {
  return LANGUAGES.find((item) => item.id === language)?.locale ?? "en-IN";
}

export function directionFor(language: Language): TextDirection {
  return LANGUAGES.find((item) => item.id === language)?.direction ?? "ltr";
}

export function nativeNameFor(language: Language): string {
  return LANGUAGES.find((item) => item.id === language)?.native ?? language;
}

const SCRIPT_PATTERN: Record<Language, RegExp> = {
  en: /[A-Za-z]/,
  hi: /[\u0900-\u097F]/,
  kn: /[\u0C80-\u0CFF]/,
  ur: /[\u0600-\u06FF]/,
};

/** True when the text is written in the script of the explanation language. */
export function matchesScript(text: string, language: Language): boolean {
  return SCRIPT_PATTERN[language].test(text);
}

/**
 * What to send to read-aloud. An English label beside an Urdu explanation would be
 * spoken as Urdu and sound broken, so a sentence in the wrong script is left out.
 * If nothing matches, the original text is still read rather than staying silent.
 */
export function textForSpeech(label: string, body: string, language: Language): string {
  const parts = [label, body].map((item) => item.trim()).filter(Boolean);
  const spoken = parts.filter((item) => matchesScript(item, language));
  return (spoken.length > 0 ? spoken : parts).join(". ");
}

export function isSupported(value: string | null | undefined): value is Language {
  return !!value && LANGUAGE_IDS.includes(value as Language);
}

/**
 * Wording for the language switch. Says explicitly that only the explanation changes,
 * because the one thing a user must be able to trust is that reading the guidance in
 * another language has not altered their form or the answers they typed.
 */
export const EXPLANATION_LANGUAGE_LABEL = "Explanation language";
export const EXPLANATION_LANGUAGE_HINT =
  "Changes the field descriptions only. Your uploaded form and your typed answers stay exactly as they are.";

/** Scripts the backend reports, named for display. */
export const SCRIPT_NAMES: Record<string, string> = {
  latin: "Latin",
  devanagari: "Devanagari",
  kannada: "Kannada",
  arabic: "Arabic / Urdu",
};

export function scriptLabel(script: string): string {
  return SCRIPT_NAMES[script] ?? script;
}
