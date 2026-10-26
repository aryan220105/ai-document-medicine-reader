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
  const progress = Math.max(((current + 1) / ORDER.length) * 100, 12);

  return (
    <div className="mx-auto max-w-xl animate-rise space-y-6 rounded-3xl border border-softline bg-foam p-6 shadow-soft">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.16em] text-leaf">Working</p>
        <h2 className="mt-2 font-display text-3xl text-ink">Reading your form</h2>
        <p className="mt-2 text-sm text-pine/80">This usually takes a few seconds. Keep this tab open.</p>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-mist">
        <div className="h-full rounded-full bg-leaf transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>
      <ol className="space-y-3" data-testid="processing-stages">
        {ORDER.map((item, index) => {
          const done = index < current;
          const active = index === current;
          return (
            <li
              key={item}
              className={`flex items-center gap-3 rounded-xl px-3 py-2 ${
                active ? "bg-mist font-semibold text-leafdark" : done ? "text-ink" : "text-slate-500"
              }`}
            >
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                  active
                    ? "animate-pulse-soft bg-leaf text-white"
                    : done
                      ? "bg-leaf/15 text-leafdark"
                      : "bg-white text-slate-400"
                }`}
              >
                {done ? "✓" : index + 1}
              </span>
              <span>{STAGE_LABELS[item]}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
