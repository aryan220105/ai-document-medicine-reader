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
  provider?: "elevenlabs" | "browser";
  configured?: boolean;
  loading?: boolean;
  error?: string | null;
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
  provider,
  configured,
  loading,
  error,
  question,
  onQuestion,
  onAsk,
  askAnswer,
}: Props) {
  if (!field) {
    return (
      <p className="p-5 text-pine/80">
        Tap a highlighted box on the form, or pick a field from the checklist, to see what to write.
      </p>
    );
  }

  const availableLanguages = bundle ? (Object.keys(bundle.languages) as Language[]) : undefined;
  // The printed label keeps its own reading direction: it is the form's content, not ours.
  const labelLanguage = field.label_language ?? bundle?.label_language ?? "en";

  return (
    <aside className="space-y-4 overflow-auto p-4" data-testid="guidance-panel">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-leaf">Current field</p>
        <DirectionalText as="h2" language={labelLanguage} className="mt-1 font-display text-2xl text-ink">
          {fieldTitle(field)}
        </DirectionalText>
      </div>
      {field.caption && field.caption !== fieldTitle(field) ? (
        <p className="-mt-2 text-xs text-pine/80">
          Printed on the form as <span dir="auto">“{field.caption}”</span>
          {field.column_header ? (
            <>
              {" "}
              under <span dir="auto">“{field.column_header}”</span>
            </>
          ) : null}
        </p>
      ) : null}
      {field.filled_by === "office" ? (
        <p role="note" className="rounded-xl bg-mist p-3 text-sm text-ink" data-testid="office-notice">
          This part is filled in by the office, not by you. Leave it blank.
        </p>
      ) : null}

      <LanguageSelector value={language} onChange={onLanguage} available={availableLanguages} />

      {field.confidence < 0.55 ? (
        <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-900">
          Low-confidence detection. Verify this box against the printed form.
        </p>
      ) : null}

      {guidance ? (
        <div className="space-y-3 rounded-2xl border border-softline bg-mist/40 p-3" data-testid="guidance-body" data-language={language}>
          <div className="flex flex-wrap gap-2">
            <SourceBadge source={guidance.source} />
            <ConfidenceBadge value={guidance.confidence} verify={guidance.requires_verification} />
            {guidance.inferred ? (
              <span className="fs-chip bg-amber-100 text-amber-900" data-testid="inferred-badge">
                Inferred from the printed wording
              </span>
            ) : null}
          </div>

          <DirectionalText language={language} className="text-lg font-semibold text-ink">
            {guidance.simple_label}
          </DirectionalText>
          <DirectionalText language={language} className="leading-relaxed text-pine">
            {guidance.what_to_enter}
          </DirectionalText>
          {guidance.why_needed ? (
            <DirectionalText language={language} className="text-sm text-pine/85">
              {guidance.why_needed}
            </DirectionalText>
          ) : null}
          {guidance.example ? (
            <p className="rounded-xl bg-foam px-3 py-2 text-sm text-ink">
              <strong>Example (fictional):</strong> <span dir="auto">{guidance.example}</span>
            </p>
          ) : null}
          {guidance.format_hint ? (
            <DirectionalText language={language} className="text-sm text-pine">
              {guidance.format_hint}
            </DirectionalText>
          ) : null}
          {guidance.verify_notice ? (
            <DirectionalText language={language} className="text-xs text-pine/75">
              {guidance.verify_notice}
            </DirectionalText>
          ) : null}

          <VoiceButton
            onPlay={onPlay}
            onStop={onStop}
            speaking={speaking}
            available={available}
            hasLanguageVoice={hasLanguageVoice}
            language={language}
            canSpeak={canSpeak}
            voiceLanguage={voiceLanguage}
            provider={provider}
            configured={configured}
            loading={loading}
            error={error}
          />
        </div>
      ) : (
        <p className="text-sm text-pine/80">Loading guidance…</p>
      )}

      <div className="rounded-2xl border border-leaf/25 bg-leaf/5 p-3">
        <FieldInput field={field} value={value} onChange={onChange} />
      </div>

      <div className="rounded-2xl border border-softline bg-white p-3">
        <label className="fs-label" htmlFor="ask">
          Ask about this field
        </label>
        <input
          id="ask"
          className="fs-field"
          value={question}
          onChange={(event) => onQuestion(event.target.value)}
          placeholder="e.g. Where should I write this?"
        />
        <button type="button" className="fs-btn-secondary mt-2" onClick={onAsk}>
          Ask
        </button>
        {askAnswer ? (
          <DirectionalText language={language} className="mt-2 text-sm text-pine">
            {askAnswer}
          </DirectionalText>
        ) : null}
      </div>
    </aside>
  );
}
