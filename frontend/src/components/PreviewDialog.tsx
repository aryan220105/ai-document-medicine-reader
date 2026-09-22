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
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-slate-900/50 p-4" role="dialog" aria-label="Completed reference preview">
      <div className="w-full max-w-lg rounded-lg bg-white p-5">
        <h2 className="font-serif text-xl">Completed Reference Preview</h2>
        <p className="mt-2 text-sm text-slate-700">
          Review this copy, then write the answers onto the official form. FormSathi does not submit anything.
        </p>
        {preview.warnings.length ? (
          <ul className="mt-3 list-disc pl-5 text-sm text-red-800">
            {preview.warnings.map((item) => (
              <li key={`${item.field_id}-${item.code}`}>{item.message}</li>
            ))}
          </ul>
        ) : null}
        {preview.pdf_url ? (
          <a className="mt-4 inline-block rounded bg-teal-800 px-4 py-2 text-white" href={preview.pdf_url} download>
            Download PDF
          </a>
        ) : (
          <p className="mt-3 text-sm">Correct overflow warnings before a PDF can be created.</p>
        )}
        <button type="button" className="ml-3 mt-4 text-slate-700 underline" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
