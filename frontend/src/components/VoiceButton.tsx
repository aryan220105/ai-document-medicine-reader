import { Loader2, Square, Volume2 } from "lucide-react";
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
  provider?: "elevenlabs" | "browser";
  configured?: boolean;
  loading?: boolean;
  error?: string | null;
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
  provider = "browser",
  configured = false,
  loading = false,
  error = null,
}: Props) {
  if (!available && provider !== "elevenlabs") {
    return <p className="text-sm text-slate-600">Voice is not available in this browser. Text guidance remains below.</p>;
  }

  const name = language ? nativeNameFor(language) : "this language";
  const busy = speaking || loading;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          aria-label="Play guidance"
          className="inline-flex items-center gap-2 rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white disabled:opacity-40"
          onClick={onPlay}
          disabled={!canSpeak || loading}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Volume2 className="h-4 w-4" />}
          {loading ? "Preparing" : speaking ? "Reading" : "Listen"}
        </button>
        <button
          type="button"
          aria-label="Stop guidance"
          className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-40"
          onClick={onStop}
          disabled={!busy}
        >
          <Square className="h-4 w-4" />
          Stop
        </button>
      </div>
      {provider === "elevenlabs" ? (
        <p className="text-sm text-slate-600" data-testid="elevenlabs-notice">
          {name} is read aloud by ElevenLabs. Only this explanation is sent, not your answers or the form.
        </p>
      ) : null}
      {provider !== "elevenlabs" && configured && canSpeak ? (
        <p className="text-sm text-slate-600" data-testid="substitute-voice-notice">
          ElevenLabs audio did not play, so this device voice is being used
          {voiceLanguage ? ` (${voiceLanguage})` : ""}.
        </p>
      ) : null}
      {provider !== "elevenlabs" && !configured && !hasLanguageVoice && canSpeak ? (
        <p className="text-sm text-slate-600" data-testid="substitute-voice-notice">
          ElevenLabs is not configured, and this device has no {name} voice, so the reading uses the closest one installed
          {voiceLanguage ? ` (${voiceLanguage})` : ""}. Add an ElevenLabs key to hear {name}. Pronunciation is approximate until then.
        </p>
      ) : null}
      {!canSpeak ? (
        <p className="text-sm text-slate-600" data-testid="no-voice-notice">
          Nothing can read {name} aloud on this device. The text below is complete.
        </p>
      ) : null}
      {error ? (
        <p className="text-sm text-red-800" role="status">
          {error}
        </p>
      ) : null}
    </div>
  );
}
