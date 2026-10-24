import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { requestSpeech } from "../api/client";
import { localeFor } from "../utils/languages";
import type { Language } from "../types";

/**
 * Voices to try, in order, when ElevenLabs is not configured and the exact language
 * is not installed. This is only a fallback. Kannada and Urdu are spoken by ElevenLabs
 * when a key is set, including on known forms.
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
  return matching.find((voice) => voice.localService) ?? matching[0];
}

export function useSpeech(language: Language, speechConfigured = false) {
  const [speaking, setSpeaking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [fellBack, setFellBack] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrl = useRef<string | null>(null);
  const requestId = useRef(0);

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      return;
    }
    const synthesis = window.speechSynthesis;
    const refresh = () => setVoices(synthesis.getVoices());
    refresh();
    synthesis.addEventListener?.("voiceschanged", refresh);
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
    return { voice: voices[0] ?? null, exact: false };
  }, [voices, language]);

  const browserSupported = typeof window !== "undefined" && "speechSynthesis" in window;

  const releaseAudio = useCallback(() => {
    const audio = audioRef.current;
    audioRef.current = null;
    if (audio) {
      // Clearing src fires an error event. That is this function stopping the
      // clip, not a failure of ElevenLabs, so the handlers must be gone first.
      audio.onerror = null;
      audio.onended = null;
      audio.pause();
      audio.src = "";
    }
    if (objectUrl.current) {
      URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = null;
    }
  }, []);

  useEffect(() => {
    requestId.current += 1;
    setError(null);
    setFellBack(false);
    releaseAudio();
    if (browserSupported) {
      window.speechSynthesis.cancel();
    }
    setSpeaking(false);
    setLoading(false);
  }, [browserSupported, language, releaseAudio]);

  const stop = useCallback(() => {
    requestId.current += 1;
    releaseAudio();
    if (browserSupported) {
      window.speechSynthesis.cancel();
    }
    setSpeaking(false);
    setLoading(false);
  }, [browserSupported, releaseAudio]);

  const browserSpeak = useCallback(
    (text: string) => {
      if (!browserSupported || !chosen.voice) {
        setFellBack(true);
        setSpeaking(false);
        return;
      }
      const synthesis = window.speechSynthesis;
      synthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = chosen.voice;
      utterance.lang = chosen.exact ? localeFor(language) : chosen.voice.lang;
      utterance.rate = chosen.exact ? 0.95 : 0.85;
      utterance.onend = () => setSpeaking(false);
      utterance.onerror = () => setSpeaking(false);
      setFellBack(true);
      setSpeaking(true);
      synthesis.speak(utterance);
    },
    [browserSupported, chosen, language],
  );

  const speak = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) {
        return;
      }
      stop();
      const token = requestId.current;
      setError(null);
      if (!speechConfigured) {
        browserSpeak(trimmed);
        return;
      }
      setLoading(true);
      setFellBack(false);
      void requestSpeech(trimmed, language)
        .then(async (blob) => {
          if (token !== requestId.current) {
            return;
          }
          const url = URL.createObjectURL(blob);
          objectUrl.current = url;
          const audio = new Audio(url);
          audioRef.current = audio;
          audio.onended = () => {
            setSpeaking(false);
            releaseAudio();
          };
          audio.onerror = () => {
            releaseAudio();
            setError("Read-aloud audio could not be played.");
            browserSpeak(trimmed);
          };
          setLoading(false);
          setSpeaking(true);
          await audio.play();
        })
        .catch((err: unknown) => {
          setLoading(false);
          const message = err instanceof Error ? err.message : "Read-aloud could not be generated.";
          setError(message);
          browserSpeak(trimmed);
        });
    },
    [browserSpeak, language, releaseAudio, speechConfigured, stop],
  );

  const usingElevenLabs = speechConfigured && !fellBack;

  return {
    speak,
    stop,
    speaking,
    loading,
    error,
    available: usingElevenLabs || (browserSupported && voices.length > 0),
    hasLanguageVoice: usingElevenLabs || chosen.exact,
    voiceName: usingElevenLabs ? "ElevenLabs" : (chosen.voice?.name ?? ""),
    voiceLanguage: usingElevenLabs ? localeFor(language) : (chosen.voice?.lang ?? ""),
    canSpeak: usingElevenLabs || Boolean(chosen.voice),
    provider: usingElevenLabs ? ("elevenlabs" as const) : ("browser" as const),
  };
}
