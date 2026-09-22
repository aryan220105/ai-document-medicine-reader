import { useMemo, useState } from "react";
import { localeFor } from "../utils/languages";
import type { Language } from "../types";

export function useSpeech(language: Language) {
  const [speaking, setSpeaking] = useState(false);
  const voice = useMemo(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      return null;
    }
    const locale = localeFor(language);
    const voices = window.speechSynthesis.getVoices();
    return voices.find((item) => item.lang.toLowerCase().startsWith(locale.slice(0, 2))) ?? null;
  }, [language, speaking]);

  const available = typeof window !== "undefined" && "speechSynthesis" in window && Boolean(voice || window.speechSynthesis.getVoices().length);

  function speak(text: string) {
    if (!window.speechSynthesis) {
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = localeFor(language);
    if (voice) {
      utterance.voice = voice;
    }
    utterance.onend = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  function stop() {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  }

  return { speak, stop, speaking, available, hasLanguageVoice: Boolean(voice) };
}
