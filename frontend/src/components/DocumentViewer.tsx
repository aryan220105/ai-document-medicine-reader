import { useEffect, useRef, useState } from "react";
import type { BoundingBox } from "../types";
import { HighlightOverlay } from "./HighlightOverlay";

interface Props {
  originalUrl: string;
  processedUrl?: string | null;
  highlights: BoundingBox[];
  preferProcessed: boolean;
}

export function DocumentViewer({ originalUrl, processedUrl, highlights, preferProcessed }: Props) {
  const [mode, setMode] = useState<"original" | "enhanced">(preferProcessed && processedUrl ? "enhanced" : "original");
  const [zoom, setZoom] = useState(1);
  const frameRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if ((preferProcessed || highlights.length > 0) && processedUrl) {
      setMode("enhanced");
    }
  }, [preferProcessed, processedUrl, highlights.length]);

  useEffect(() => {
    if (highlights.length) {
      frameRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlights]);

  const src = mode === "enhanced" && processedUrl ? processedUrl : originalUrl;

  return (
    <section className="rounded-2xl border border-sand bg-white p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="inline-flex rounded-full bg-sand p-1" role="tablist" aria-label="Image version">
          <button
            type="button"
            className={`rounded-full px-4 py-2 ${mode === "original" ? "bg-white font-semibold" : ""}`}
            onClick={() => setMode("original")}
          >
            Original
          </button>
          <button
            type="button"
            className={`rounded-full px-4 py-2 disabled:opacity-50 ${mode === "enhanced" ? "bg-white font-semibold" : ""}`}
            onClick={() => setMode("enhanced")}
            disabled={!processedUrl}
          >
            Enhanced
          </button>
        </div>
        <div className="flex gap-2">
          <button type="button" className="rounded-full border px-3 py-1" onClick={() => setZoom((value) => Math.max(1, value - 0.25))} aria-label="Zoom out">
            -
          </button>
          <button type="button" className="rounded-full border px-3 py-1" onClick={() => setZoom((value) => Math.min(3, value + 0.25))} aria-label="Zoom in">
            +
          </button>
        </div>
      </div>
      <div ref={frameRef} className="overflow-auto rounded-xl bg-slate-100">
        <div className="relative inline-block min-w-full origin-top-left" style={{ transform: `scale(${zoom})` }}>
          <img src={src} alt="Uploaded document" className="mx-auto block max-h-[70vh] w-full object-contain" />
          <HighlightOverlay highlights={highlights} />
        </div>
      </div>
      {processedUrl ? (
        <p className="mt-3 text-sm text-slate-600">
          Highlights are aligned to the enhanced OCR image, not guessed from the original photo.
        </p>
      ) : null}
    </section>
  );
}
