import type { PreviewResult } from "../types";

interface Props {
  preview: PreviewResult | null;
  onClose: () => void;
}

export function PreviewDialog({ preview, onClose }: Props) {
  if (!preview) {
    return null;
  }
  return (
    <div
      className="fixed inset-0 z-20 flex items-center justify-center bg-ink/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-label="Completed reference preview"
    >
      <div className="w-full max-w-lg animate-rise rounded-3xl border border-softline bg-foam p-6 shadow-soft">
        <h2 className="font-display text-2xl text-ink">Completed Reference Preview</h2>
        <p className="mt-2 text-sm text-pine">
          Review this copy, then write the answers onto the official form. FormSathi does not submit anything.
        </p>
        {preview.warnings.length ? (
          <ul className="mt-3 list-disc pl-5 text-sm text-red-800">
            {preview.warnings.map((item) => (
              <li key={`${item.field_id}-${item.code}`}>{item.message}</li>
            ))}
          </ul>
        ) : null}
        <div className="mt-5 flex flex-wrap items-center gap-3">
          {preview.pdf_url ? (
            <a className="fs-btn-primary" href={preview.pdf_url} download>
              Download PDF
            </a>
          ) : (
            <p className="text-sm text-pine">Correct overflow warnings before a PDF can be created.</p>
          )}
          <button type="button" className="fs-btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
