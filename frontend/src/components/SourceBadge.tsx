import type { GuidanceSource } from "../types";

const LABELS: Record<GuidanceSource, string> = {
  known_form_knowledge_base: "Known Form Knowledge Base",
  common_field_dictionary: "Common Field Dictionary",
  printed_form_text: "Printed Form Text",
  label_pattern_heuristic: "Inferred From Printed Label",
  page_interpretation: "Read From This Page",
  general_ai_guidance: "General AI Guidance",
  unavailable: "Guidance unavailable",
};

export function SourceBadge({ source }: { source: GuidanceSource }) {
  return (
    <span className="fs-chip bg-white text-pine ring-1 ring-softline" data-testid="source-badge">
      {LABELS[source]}
    </span>
  );
}
