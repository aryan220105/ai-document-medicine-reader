import { Square, Volume2 } from "lucide-react";
import type { Language } from "../types";
import { nativeNameFor } from "../utils/languages";

interface Props {
  onPlay: () => void;
  onStop: () => void;
  speaking: boolean;
  available: boolean;
  hasLanguageVoice: boolean;
  language?: Language;
  canSpeak?: boolean;
  voiceLanguage?: string;
}

export function VoiceButton({
  onPlay,
  onStop,
  speaking,
  available,
  hasLanguageVoice,
  language,
  canSpeak = true,
  voiceLanguage = "",
}: Props) {
  if (!available) {
    return <p className="text-sm text-slate-600">Voice is not available in this browser. Text guidance remains below.</p>;
  }

  const name = language ? nativeNameFor(language) : "this language";
  return (
    <div className="space-y-1">
      <div className="flex gap-2">
        <button
          type="button"
          aria-label="Play guidance"
          className="rounded border border-slate-300 px-3 py-2 disabled:opacity-40"
          onClick={onPlay}
          disabled={!canSpeak}
        >
          <Volume2 className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="Stop guidance"
          className="rounded border border-slate-300 px-3 py-2 disabled:opacity-40"
          onClick={onStop}
          disabled={!speaking}
        >
          <Square className="h-4 w-4" />
        </button>
      </div>
      {!hasLanguageVoice && canSpeak ? (
        // Reading Kannada or Urdu with a stand-in voice is imperfect, but it is speech
        // rather than silence. Saying which voice is doing the reading is what keeps that
        // honest, rather than letting it sound like a bad translation.
        <p className="text-sm text-slate-600" data-testid="substitute-voice-notice">
          This device has no {name} voice, so the reading uses the closest one installed
          {voiceLanguage ? ` (${voiceLanguage})` : ""}. Pronunciation will be approximate. On Windows you can add a
          {" "}
          {name} voice under Settings → Time &amp; language → Speech.
        </p>
      ) : null}
      {!canSpeak ? (
        <p className="text-sm text-slate-600" data-testid="no-voice-notice">
          This device has no speech voices installed, so nothing can be read aloud. The text below is complete.
        </p>
      ) : null}
    </div>
  );
}
