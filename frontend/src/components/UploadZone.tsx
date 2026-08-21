import { useRef, useState } from "react";
import { FileUp, Pill, ScrollText } from "lucide-react";
import { validateImageFile } from "../utils/validation";

interface Props {
  maxMb: number;
  onFile: (file: File) => void;
  disabled?: boolean;
}

export function UploadZone({ maxMb, onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  function handleFile(file: File | undefined) {
    if (!file) {
      return;
    }
    const message = validateImageFile(file, maxMb);
    setError(message);
    if (!message) {
      onFile(file);
    }
  }

  return (
    <section className="mx-auto max-w-5xl px-4 pb-16">
      <div className="mb-8 grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-sand bg-white p-6 shadow-sm">
          <Pill className="h-8 w-8 text-moss" aria-hidden />
          <h2 className="mt-4 font-serif text-2xl">Medicine Label</h2>
          <p className="mt-2 text-slate-600">Read dosage, expiry date, warnings and medicine information.</p>
        </article>
        <article className="rounded-2xl border border-sand bg-white p-6 shadow-sm">
          <ScrollText className="h-8 w-8 text-moss" aria-hidden />
          <h2 className="mt-4 font-serif text-2xl">General Document</h2>
          <p className="mt-2 text-slate-600">Understand bills, notices, insurance letters and government documents.</p>
        </article>
      </div>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          handleFile(event.dataTransfer.files[0]);
        }}
        className={`rounded-3xl border-2 border-dashed p-10 text-center transition ${
          dragOver ? "border-moss bg-white" : "border-moss/30 bg-white/70"
        }`}
      >
        <FileUp className="mx-auto h-10 w-10 text-moss" aria-hidden />
        <p className="mt-4 text-lg font-medium">Drop a document photo here</p>
        <p className="mt-1 text-slate-600">PNG, JPG, JPEG, or WEBP. Maximum {maxMb} MB.</p>
        <button
          type="button"
          className="mt-6 rounded-full bg-moss px-6 py-3 font-semibold text-white hover:bg-mossdark disabled:opacity-60"
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
        >
          Upload Document
        </button>
        <input
          ref={inputRef}
          className="sr-only"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          aria-label="Upload document image"
          onChange={(event) => handleFile(event.target.files?.[0])}
        />
        {error ? (
          <p role="alert" className="mt-4 text-clay">
            {error}
          </p>
        ) : null}
      </div>
    </section>
  );
}
