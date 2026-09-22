import { ConfidenceBadge } from "./ConfidenceBadge";
import { FieldInput } from "./FieldInput";
import { SourceBadge } from "./SourceBadge";
import { VoiceButton } from "./VoiceButton";
import type { DetectedField, FieldGuidance } from "../types";

interface Props {
  field: DetectedField | null;
  guidance: FieldGuidance | null;
  value: string;
  onChange: (value: string) => void;
  onPlay: () => void;
  onStop: () => void;
  speaking: boolean;
  available: boolean;
  hasLanguageVoice: boolean;
  question: string;
  onQuestion: (value: string) => void;
  onAsk: () => void;
  askAnswer: string;
}

export function GuidancePanel({
  field,
  guidance,
  value,
  onChange,
  onPlay,
  onStop,
  speaking,
  available,
  hasLanguageVoice,
  question,
  onQuestion,
  onAsk,
  askAnswer,
}: Props) {
  if (!field) {
    return <p className="p-4 text-slate-600">Select a field on the form to see guidance.</p>;
  }
  return (
    <aside className="space-y-4 overflow-auto p-4" data-testid="guidance-panel">
      <h2 className="font-serif text-xl">{guidance?.simple_label || field.label || "Field"}</h2>
      {field.confidence < 0.55 ? (
        <p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-900">
          Low-confidence detection. Verify this box against the printed form.
        </p>
      ) : null}
      {guidance ? (
        <>
          <div className="flex flex-wrap gap-2">
            <SourceBadge source={guidance.source} />
            <ConfidenceBadge value={guidance.confidence} verify={guidance.requires_verification} />
          </div>
          <p>{guidance.what_to_enter}</p>
          {guidance.why_needed ? <p className="text-sm text-slate-700">{guidance.why_needed}</p> : null}
          {guidance.example ? <p className="text-sm"><strong>Example (fictional):</strong> {guidance.example}</p> : null}
          {guidance.format_hint ? <p className="text-sm">Format: {guidance.format_hint}</p> : null}
          <VoiceButton onPlay={onPlay} onStop={onStop} speaking={speaking} available={available} hasLanguageVoice={hasLanguageVoice} />
        </>
      ) : (
        <p>Loading guidance…</p>
      )}
      <FieldInput field={field} value={value} onChange={onChange} />
      <div>
        <label className="block text-sm font-medium" htmlFor="ask">
          Ask about this field
        </label>
        <input id="ask" className="mt-1 w-full rounded-md border px-3 py-2" value={question} onChange={(event) => onQuestion(event.target.value)} />
        <button type="button" className="mt-2 rounded bg-slate-800 px-3 py-2 text-white" onClick={onAsk}>
          Ask
        </button>
        {askAnswer ? <p className="mt-2 text-sm">{askAnswer}</p> : null}
      </div>
    </aside>
  );
}
