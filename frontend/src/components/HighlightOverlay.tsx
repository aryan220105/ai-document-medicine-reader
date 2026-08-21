import type { BoundingBox } from "../types";

interface Props {
  highlights: BoundingBox[];
}

export function HighlightOverlay({ highlights }: Props) {
  return (
    <div className="pointer-events-none absolute inset-0" data-testid="highlight-overlay">
      {highlights.map((box, index) => (
        <div
          key={`${box.x}-${box.y}-${index}`}
          className="absolute rounded-sm border-2 border-amber-500 bg-amber-300/35 shadow-[0_0_0_1px_rgba(180,83,58,0.35)]"
          style={{
            left: `${Number((box.x * 100).toFixed(4))}%`,
            top: `${Number((box.y * 100).toFixed(4))}%`,
            width: `${Number((box.width * 100).toFixed(4))}%`,
            height: `${Number((box.height * 100).toFixed(4))}%`,
          }}
        >
          {box.label ? (
            <span className="absolute -top-6 left-0 whitespace-nowrap rounded bg-ink px-2 py-0.5 text-xs text-white">
              {box.label}
            </span>
          ) : null}
        </div>
      ))}
    </div>
  );
}
