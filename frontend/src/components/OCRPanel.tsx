interface Props {
  text: string;
  confidence: number;
  level: string;
}

export function OCRPanel({ text, confidence, level }: Props) {
  async function copy() {
    await navigator.clipboard.writeText(text);
  }
  return (
    <section className="rounded-2xl border border-sand bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-serif text-xl">Extracted Text</h2>
        <div className="flex items-center gap-3">
          <span className="rounded-full bg-sand px-3 py-1 text-sm">
            OCR confidence: {confidence.toFixed(1)} ({level})
          </span>
          <button type="button" className="rounded-full border px-4 py-2" onClick={copy}>
            Copy OCR Text
          </button>
        </div>
      </div>
      <pre className="mt-4 max-h-56 overflow-auto whitespace-pre-wrap rounded-xl bg-paper p-4 font-sans text-sm leading-6">
        {text || "No readable text was detected."}
      </pre>
    </section>
  );
}
