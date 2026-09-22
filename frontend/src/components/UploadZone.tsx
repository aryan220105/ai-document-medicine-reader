import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { LanguageSelector } from "./LanguageSelector";
import { PrivacyNotice } from "./PrivacyNotice";
import type { AppConfig, DocumentCategory, Language } from "../types";

const CATEGORIES: DocumentCategory[] = ["government", "banking", "insurance", "education", "financial", "other"];

interface Props {
  config: AppConfig | null;
  language: Language;
  onLanguage: (language: Language) => void;
  category: DocumentCategory;
  onCategory: (category: DocumentCategory) => void;
  allowAi: boolean;
  onAllowAi: (value: boolean) => void;
  onFile: (file: File) => void;
  onDemo: () => void;
  error: string | null;
}

export function UploadZone({
  config,
  language,
  onLanguage,
  category,
  onCategory,
  allowAi,
  onAllowAi,
  onFile,
  onDemo,
  error,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  function accept(file: File | undefined) {
    if (file) {
      onFile(file);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <p className="text-sm uppercase tracking-wide text-teal-800">Academic demonstration</p>
        <h1 className="mt-1 font-serif text-3xl text-slate-900">FormSathi</h1>
        <p className="mt-2 text-slate-700">
          Upload a form, see where each answer belongs, and hear simple guidance in English, Hindi, or Kannada.
        </p>
      </header>
      <div
        className={`rounded-lg border-2 border-dashed px-6 py-10 text-center ${drag ? "border-teal-700 bg-teal-50" : "border-slate-300 bg-white"}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDrag(false);
          accept(event.dataTransfer.files[0]);
        }}
      >
        <Upload className="mx-auto h-8 w-8 text-teal-800" aria-hidden />
        <p className="mt-3 font-medium">Drop a PNG, JPG, WEBP, or PDF here</p>
        <p className="mt-1 text-sm text-slate-600">Maximum {config?.max_upload_mb ?? 10} MB. Up to {config?.max_pdf_pages ?? 5} PDF pages.</p>
        <button
          type="button"
          className="mt-4 rounded-md bg-teal-800 px-4 py-2 text-white"
          onClick={() => inputRef.current?.click()}
        >
          Choose file
        </button>
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          accept=".png,.jpg,.jpeg,.webp,.pdf"
          onChange={(event) => accept(event.target.files?.[0])}
        />
      </div>
      {error ? <p role="alert" className="text-red-800">{error}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm font-medium text-slate-700">
          Form category
          <select
            className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 capitalize"
            value={category}
            onChange={(event) => onCategory(event.target.value as DocumentCategory)}
          >
            {CATEGORIES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <LanguageSelector value={language} onChange={onLanguage} />
      </div>
      <PrivacyNotice
        notice={config?.privacy_notice ?? "Uploaded forms stay on this machine for the demonstration."}
        allowAi={allowAi}
        aiEnabled={Boolean(config?.llm_configured)}
        onAllowAi={onAllowAi}
      />
      <button type="button" className="text-teal-800 underline" onClick={onDemo}>
        Try a synthetic Demo Bank form
      </button>
    </div>
  );
}
