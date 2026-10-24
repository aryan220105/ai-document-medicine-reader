import { ConfidenceBadge } from "./ConfidenceBadge";
import { DirectionalText } from "./DirectionalText";
import { FieldInput } from "./FieldInput";
import { LanguageSelector } from "./LanguageSelector";
import { SourceBadge } from "./SourceBadge";
import { VoiceButton } from "./VoiceButton";
import type { DetectedField, FieldGuidance, Language, MultilingualFieldGuidance } from "../types";
import { fieldTitle } from "./FieldNavigator";

interface Props {
  field: DetectedField | null;
  guidance: FieldGuidance | null;
  bundle: MultilingualFieldGuidance | null;
  language: Language;
  onLanguage: (language: Language) => void;
  value: string;
  onChange: (value: string) => void;
  onPlay: () => void;
  onStop: () => void;
  speaking: boolean;
  available: boolean;
  hasLanguageVoice: boolean;
  canSpeak?: boolean;
  voiceLanguage?: string;
  question: string;
  onQuestion: (value: string) => void;
  onAsk: () => void;
  askAnswer: string;
}

export function GuidancePanel({
  field,
  guidance,
  bundle,
  language,
  onLanguage,
  value,
  onChange,
  onPlay,
  onStop,
  speaking,
  available,
  hasLanguageVoice,
  canSpeak,
  voiceLanguage,
  question,
  onQuestion,
  onAsk,
  askAnswer,
}: Props) {
  if (!field) {
    return <p className="p-4 text-slate-600">Select a field on the form to see guidance.</p>;
  }

  const availableLanguages = bundle ? (Object.keys(bundle.languages) as Language[]) : undefined;
  // The printed label keeps its own reading direction: it is the form's content, not ours.
  const labelLanguage = field.label_language ?? bundle?.label_language ?? "en";

  return (
    <aside className="space-y-4 overflow-auto p-4" data-testid="guidance-panel">
      <DirectionalText as="h2" language={labelLanguage} className="font-serif text-xl">
        {fieldTitle(field)}
      </DirectionalText>
      {field.caption && field.caption !== fieldTitle(field) ? (
        <p className="-mt-2 text-xs text-slate-600">
          Printed on the form as <span dir="auto">“{field.caption}”</span>
          {field.column_header ? (
            <>
              {" "}under <span dir="auto">“{field.column_header}”</span>
            </>
          ) : null}
        </p>
      ) : null}
      {field.filled_by === "office" ? (
        <p role="note" className="rounded bg-slate-100 p-2 text-sm text-slate-800" data-testid="office-notice">
          This part is filled in by the office, not by you. Leave it blank.
        </p>
      ) : null}

      <LanguageSelector value={language} onChange={onLanguage} available={availableLanguages} />

      {field.confidence < 0.55 ? (
        <p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-900">
          Low-confidence detection. Verify this box against the printed form.
        </p>
      ) : null}

      {guidance ? (
        <div data-testid="guidance-body" data-language={language}>
          <div className="mb-2 flex flex-wrap gap-2">
            <SourceBadge source={guidance.source} />
            <ConfidenceBadge value={guidance.confidence} verify={guidance.requires_verification} />
            {guidance.inferred ? (
              <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-900" data-testid="inferred-badge">
                Inferred from the printed wording
              </span>
            ) : null}
          </div>

          <DirectionalText language={language} className="font-medium">
            {guidance.simple_label}
          </DirectionalText>
          <DirectionalText language={language}>{guidance.what_to_enter}</DirectionalText>
          {guidance.why_needed ? (
            <DirectionalText language={language} className="text-sm text-slate-700">
              {guidance.why_needed}
            </DirectionalText>
          ) : null}
          {guidance.example ? (
            <p className="text-sm">
              <strong>Example (fictional):</strong> <span dir="ltr">{guidance.example}</span>
            </p>
          ) : null}
          {guidance.format_hint ? (
            <DirectionalText language={language} className="text-sm">
              {guidance.format_hint}
            </DirectionalText>
          ) : null}
          {guidance.verify_notice ? (
            <DirectionalText language={language} className="mt-2 text-xs text-slate-600">
              {guidance.verify_notice}
            </DirectionalText>
          ) : null}

          <div className="mt-3">
            <VoiceButton
              onPlay={onPlay}
              onStop={onStop}
              speaking={speaking}
              available={available}
              hasLanguageVoice={hasLanguageVoice}
              language={language}
              canSpeak={canSpeak}
              voiceLanguage={voiceLanguage}
            />
          </div>
        </div>
      ) : (
        <p>Loading guidance…</p>
      )}

      <FieldInput field={field} value={value} onChange={onChange} />

      <div>
        <label className="block text-sm font-medium" htmlFor="ask">
          Ask about this field
        </label>
        <input
          id="ask"
          className="mt-1 w-full rounded-md border px-3 py-2"
          value={question}
          onChange={(event) => onQuestion(event.target.value)}
        />
        <button type="button" className="mt-2 rounded bg-slate-800 px-3 py-2 text-white" onClick={onAsk}>
          Ask
        </button>
        {askAnswer ? (
          <DirectionalText language={language} className="mt-2 text-sm">
            {askAnswer}
          </DirectionalText>
        ) : null}
      </div>
    </aside>
  );
}
