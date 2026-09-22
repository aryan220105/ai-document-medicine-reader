import type { GuidanceSource } from "../types";

const LABELS: Record<GuidanceSource, string> = {
  known_form_knowledge_base: "Known Form Knowledge Base",
  common_field_dictionary: "Common Field Dictionary",
  printed_form_text: "Printed Form Text",
  general_ai_guidance: "General AI Guidance",
  unavailable: "Guidance unavailable",
};

export function SourceBadge({ source }: { source: GuidanceSource }) {
  return (
    <span className="inline-block rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-800" data-testid="source-badge">
      {LABELS[source]}
    </span>
  );
}
