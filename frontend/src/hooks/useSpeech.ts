import { useCallback, useEffect, useMemo, useState } from "react";
import { localeFor } from "../utils/languages";
import type { Language } from "../types";

/**
 * Voices to try, in order, when the exact language is not installed.
 *
 * Reading Kannada text with a Hindi voice is imperfect, but it is speech rather than
 * silence, and the engine's letter-to-sound rules for a related Indic language are much
 * closer than an English voice's. Urdu falls back through Arabic and Persian, which share
 * its script, before Hindi, which shares its vocabulary.
 */
const VOICE_FALLBACKS: Record<Language, string[]> = {
  en: ["en"],
  hi: ["hi", "mr", "ne", "bn", "gu", "pa", "ta", "te", "kn", "ml", "en-in", "en"],
  kn: ["kn", "te", "ta", "ml", "mr", "hi", "bn", "gu", "en-in", "en"],
  ur: ["ur", "ar", "fa", "ps", "hi", "en-in", "en"],
};

function normalise(tag: string): string {
  return tag.toLowerCase().replace("_", "-");
}

function pick(voices: SpeechSynthesisVoice[], prefix: string): SpeechSynthesisVoice | null {
  const matching = voices.filter((voice) => normalise(voice.lang).startsWith(prefix));
  if (matching.length === 0) {
    return null;
  }
  // A local voice speaks immediately; a remote one needs the network and can fail
  // silently, which looks exactly like a broken button.
  return matching.find((voice) => voice.localService) ?? matching[0];
}

export function useSpeech(language: Language) {
  const [speaking, setSpeaking] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  // The voice list is populated asynchronously, and on most browsers the first call to
  // getVoices() returns an empty array. Reading it once during render reported "no voice
  // for this language" for every language, including ones that were installed.
  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      return;
    }
    const synthesis = window.speechSynthesis;
    const refresh = () => setVoices(synthesis.getVoices());
    refresh();
    synthesis.addEventListener?.("voiceschanged", refresh);
    // Safari does not always fire voiceschanged; a couple of polls settle it.
    const timers = [250, 1000, 2500].map((delay) => window.setTimeout(refresh, delay));
    return () => {
      synthesis.removeEventListener?.("voiceschanged", refresh);
      timers.forEach(window.clearTimeout);
    };
  }, []);

  const chosen = useMemo(() => {
    if (voices.length === 0) {
      return { voice: null as SpeechSynthesisVoice | null, exact: false };
    }
    const order = VOICE_FALLBACKS[language] ?? [localeFor(language).slice(0, 2)];
    for (const [index, prefix] of order.entries()) {
      const voice = pick(voices, prefix);
      if (voice) {
        return { voice, exact: index === 0 };
      }
    }
    // Nothing in the family. Any voice is still better than a button that does nothing.
    return { voice: voices[0] ?? null, exact: false };
  }, [voices, language]);

  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const available = supported && voices.length > 0;

  const speak = useCallback(
    (text: string) => {
      if (!supported || !text.trim() || !chosen.voice) {
        return;
      }
      const synthesis = window.speechSynthesis;
      synthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = chosen.voice;
      // Keep the requested language on the utterance even when the voice is a stand-in:
      // some engines use it to choose letter-to-sound rules independently of the voice.
      utterance.lang = chosen.exact ? localeFor(language) : chosen.voice.lang;
      utterance.rate = chosen.exact ? 0.95 : 0.85;
      utterance.onend = () => setSpeaking(false);
      utterance.onerror = () => setSpeaking(false);
      setSpeaking(true);
      synthesis.speak(utterance);
    },
    [chosen, language, supported],
  );

  const stop = useCallback(() => {
    if (supported) {
      window.speechSynthesis.cancel();
    }
    setSpeaking(false);
  }, [supported]);

  return {
    speak,
    stop,
    speaking,
    available,
    /** True when a voice for this exact language is installed. */
    hasLanguageVoice: chosen.exact,
    /** The voice that will actually be used, exact or not. */
    voiceName: chosen.voice?.name ?? "",
    voiceLanguage: chosen.voice?.lang ?? "",
    /** Whether anything will be spoken at all. */
    canSpeak: Boolean(chosen.voice),
  };
}
