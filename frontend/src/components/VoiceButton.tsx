import { Square, Volume2 } from "lucide-react";

interface Props {
  onPlay: () => void;
  onStop: () => void;
  speaking: boolean;
  available: boolean;
  hasLanguageVoice: boolean;
}

export function VoiceButton({ onPlay, onStop, speaking, available, hasLanguageVoice }: Props) {
  if (!available) {
    return <p className="text-sm text-slate-600">Voice is not available in this browser. Text guidance remains below.</p>;
  }
  return (
    <div className="space-y-1">
      <div className="flex gap-2">
        <button type="button" aria-label="Play guidance" className="rounded border border-slate-300 px-3 py-2" onClick={onPlay}>
          <Volume2 className="h-4 w-4" />
        </button>
        <button type="button" aria-label="Stop guidance" className="rounded border border-slate-300 px-3 py-2" onClick={onStop} disabled={!speaking}>
          <Square className="h-4 w-4" />
        </button>
      </div>
      {!hasLanguageVoice ? <p className="text-sm text-slate-600">No matching system voice for this language. Text guidance is still available.</p> : null}
    </div>
  );
}
