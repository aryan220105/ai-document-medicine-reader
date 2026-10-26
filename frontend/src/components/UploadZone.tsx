import { useRef, useState } from "react";
import { FileUp, Sparkles } from "lucide-react";
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
    <div className="mx-auto grid max-w-5xl gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
      <section className="space-y-6 px-1">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-leaf">Academic demonstration</p>
        <h1 className="font-display text-5xl font-semibold leading-[1.05] tracking-tight text-ink sm:text-6xl">
          FormSathi
        </h1>
        <p className="max-w-xl text-lg leading-relaxed text-ink">
          Upload a form, see where each answer belongs, and hear the explanation in English, Hindi, Kannada, or Urdu.
        </p>
        <ol className="grid gap-3 sm:grid-cols-3">
          {[
            { step: "1", title: "Upload", text: "Photo or PDF of the form" },
            { step: "2", title: "Tap a box", text: "See what it asks for" },
            { step: "3", title: "Write & preview", text: "Copy onto the official form" },
          ].map((item) => (
            <li key={item.step} className="rounded-2xl border-2 border-softline bg-foam px-4 py-3">
              <p className="font-display text-2xl text-leaf">{item.step}</p>
              <p className="mt-1 font-semibold text-ink">{item.title}</p>
              <p className="mt-1 text-sm text-pine">{item.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-4">
        <div
          className={`rounded-3xl border-2 border-dashed px-6 py-10 text-center transition duration-200 ${
            drag ? "border-leaf bg-leaf/5 shadow-lift" : "border-softline bg-foam shadow-soft"
          }`}
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
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-mist text-leaf">
            <FileUp className="h-7 w-7" aria-hidden />
          </div>
          <p className="mt-4 text-lg font-semibold text-ink">Drop a PNG, JPG, WEBP, or PDF here</p>
          <p className="mt-1 text-sm text-pine/80">
            Maximum {config?.max_upload_mb ?? 10} MB. Up to {config?.max_pdf_pages ?? 5} PDF pages.
          </p>
          <button type="button" className="fs-btn-primary mt-5" onClick={() => inputRef.current?.click()}>
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

        {error ? (
          <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-900">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="fs-label">
            Form category
            <select
              className="fs-field capitalize"
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

        <button type="button" className="fs-btn-secondary w-full" onClick={onDemo}>
          <Sparkles className="h-4 w-4 text-coral" aria-hidden />
          Try a synthetic Demo Bank form
        </button>
      </section>
    </div>
  );
}
