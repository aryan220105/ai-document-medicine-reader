import type { ProcessingStage } from "../types";
import { STAGE_LABELS } from "../utils/validation";

const ORDER: ProcessingStage[] = [
  "uploading",
  "detecting",
  "enhancing",
  "ocr",
  "extracting",
  "indexing",
  "ready",
];

interface Props {
  stage: ProcessingStage;
}

export function ProcessingProgress({ stage }: Props) {
  const current = Math.max(ORDER.indexOf(stage === "failed" ? "uploading" : stage), 0);
  const percent = stage === "ready" ? 100 : Math.round(((current + 1) / ORDER.length) * 100);
  return (
    <div className="rounded-2xl border border-sand bg-white p-5" aria-live="polite">
      <div className="flex items-center justify-between gap-3">
        <p className="font-medium">{STAGE_LABELS[stage] ?? "Processing"}</p>
        <span className="text-sm text-slate-500">{percent}%</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-sand">
        <div className="h-full rounded-full bg-moss transition-all" style={{ width: `${percent}%` }} />
      </div>
      <ol className="mt-4 grid gap-1 text-sm text-slate-600 md:grid-cols-2">
        {ORDER.map((item, index) => (
          <li key={item} className={index <= current ? "text-mossdark font-medium" : ""}>
            {index + 1}. {STAGE_LABELS[item]}
          </li>
        ))}
      </ol>
    </div>
  );
}
