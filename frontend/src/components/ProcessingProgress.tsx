import { STAGE_LABELS, type ProcessingStage } from "../types";

const ORDER: ProcessingStage[] = [
  "validating",
  "preparing_pages",
  "reading_text",
  "detecting_fields",
  "matching_form",
  "ready",
];

export function ProcessingProgress({ stage }: { stage: ProcessingStage }) {
  const current = ORDER.indexOf(stage === "failed" ? "validating" : stage);
  return (
    <ol className="mx-auto max-w-xl space-y-3" data-testid="processing-stages">
      {ORDER.map((item, index) => (
        <li key={item} className={index <= current ? "font-semibold text-teal-900" : "text-slate-500"}>
          {STAGE_LABELS[item]}
        </li>
      ))}
    </ol>
  );
}
