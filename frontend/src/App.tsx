import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  askQuestion,
  createPreview,
  deleteDocument,
  fetchConfig,
  getDocument,
  getFields,
  requestGuidance,
  uploadDocument,
} from "./api/client";
import { FieldNavigator } from "./components/FieldNavigator";
import { FormViewer } from "./components/FormViewer";
import { GuidancePanel } from "./components/GuidancePanel";
import { LanguageSelector } from "./components/LanguageSelector";
import { PreviewDialog } from "./components/PreviewDialog";
import { ProcessingProgress } from "./components/ProcessingProgress";
import { UploadZone } from "./components/UploadZone";
import { useEasyRead } from "./hooks/useEasyRead";
import { useSpeech } from "./hooks/useSpeech";
import type { AppConfig, DocumentCategory, DocumentResponse, FieldGuidance, Language, PreviewResult } from "./types";
import { validateUpload } from "./utils/validation";

const LANGUAGE_KEY = "formsathi.language";

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [language, setLanguage] = useState<Language>(() => (localStorage.getItem(LANGUAGE_KEY) as Language) || "en");
  const [category, setCategory] = useState<DocumentCategory>("other");
  const [allowAi, setAllowAi] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [guidance, setGuidance] = useState<FieldGuidance | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [pageIndex, setPageIndex] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [question, setQuestion] = useState("");
  const [askAnswer, setAskAnswer] = useState("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const { easyRead, setEasyRead } = useEasyRead();
  const speech = useSpeech(language);

  useEffect(() => {
    fetchConfig().then(setConfig).catch((err: unknown) => {
      setError(err instanceof ApiError ? err.message : "The assistance service is unavailable.");
    });
  }, []);

  useEffect(() => {
    localStorage.setItem(LANGUAGE_KEY, language);
  }, [language]);

  useEffect(() => {
    if (!document || document.status !== "processing") {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const next = await getDocument(document.id);
        const fields = next.status === "ready" ? await getFields(next.id) : { fields: next.fields };
        setDocument({ ...next, fields: fields.fields });
        if (next.status === "ready" && fields.fields[0]) {
          setSelectedId(fields.fields[0].id);
        }
        if (next.status === "failed") {
          setError(next.error_message);
        }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "The assistance service is unavailable.");
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [document]);

  useEffect(() => {
    if (!document || document.status !== "ready" || !selectedId) {
      return;
    }
    requestGuidance(document.id, selectedId, language, allowAi)
      .then(setGuidance)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Guidance could not be loaded."));
  }, [document?.id, selectedId, language, allowAi, document?.status]);

  const selected = useMemo(
    () => document?.fields.find((field) => field.id === selectedId) ?? null,
    [document, selectedId],
  );

  async function handleFile(file: File) {
    const message = validateUpload(file, config?.max_upload_mb ?? 10);
    if (message) {
      setError(message);
      return;
    }
    setError(null);
    try {
      const created = await uploadDocument(file, category);
      setDocument(created);
      setAnswers({});
      setPreview(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    }
  }

  async function handleDemo() {
    const response = await fetch("/samples/demo_bank_account_opening.png");
    if (!response.ok) {
      setError("Demo sample is not available. Generate samples first.");
      return;
    }
    const blob = await response.blob();
    await handleFile(new File([blob], "demo_bank_account_opening.png", { type: "image/png" }));
  }

  async function reset() {
    if (document) {
      await deleteDocument(document.id).catch(() => undefined);
    }
    speech.stop();
    setDocument(null);
    setSelectedId(null);
    setGuidance(null);
    setAnswers({});
    setError(null);
    setPreview(null);
  }

  async function handlePreview() {
    if (!document) {
      return;
    }
    const payload = Object.entries(answers).map(([field_id, value]) => ({ field_id, value }));
    try {
      setPreview(await createPreview(document.id, payload));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Preview could not be created.");
    }
  }

  return (
    <div className={`min-h-screen ${easyRead ? "easy-read" : ""}`}>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-300 bg-white px-4 py-3">
        <div>
          <p className="font-serif text-xl text-slate-900">FormSathi</p>
          <p className="text-sm text-slate-600">AI-powered multilingual form assistant</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <LanguageSelector value={language} onChange={setLanguage} />
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={easyRead} onChange={(event) => setEasyRead(event.target.checked)} />
            Easy Read
          </label>
          {document ? (
            <button type="button" className="rounded border px-3 py-2" onClick={reset}>
              Start new form
            </button>
          ) : null}
        </div>
      </header>
      <main className="p-4">
        {error ? <p role="alert" className="mb-4 rounded bg-red-50 p-3 text-red-900">{error}</p> : null}
        {!document ? (
          <UploadZone
            config={config}
            language={language}
            onLanguage={setLanguage}
            category={category}
            onCategory={setCategory}
            allowAi={allowAi}
            onAllowAi={setAllowAi}
            onFile={handleFile}
            onDemo={handleDemo}
            error={error}
          />
        ) : document.status === "processing" ? (
          <ProcessingProgress stage={document.stage} />
        ) : document.status === "failed" ? (
          <div className="mx-auto max-w-xl space-y-3">
            <p>{document.error_message}</p>
            <button type="button" className="underline" onClick={reset}>
              Try another form
            </button>
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)_340px]">
            <div className="hidden lg:block">
              <FieldNavigator
                fields={document.fields.filter((field) => !excluded.has(field.id) || field.id === selectedId)}
                selectedId={selectedId}
                excluded={excluded}
                onSelect={(id) => {
                  setSelectedId(id);
                  const field = document.fields.find((item) => item.id === id);
                  if (field) {
                    setPageIndex(field.page_index);
                  }
                }}
                onExclude={(id) => {
                  const next = new Set(excluded);
                  if (next.has(id)) {
                    next.delete(id);
                  } else {
                    next.add(id);
                  }
                  setExcluded(next);
                }}
              />
            </div>
            <FormViewer
              documentId={document.id}
              pageIndex={pageIndex}
              pageCount={Math.max(document.page_count, 1)}
              fields={document.fields}
              selectedId={selectedId}
              answers={answers}
              zoom={zoom}
              onZoom={setZoom}
              onSelect={setSelectedId}
              onPage={setPageIndex}
            />
            <div>
              <p className="px-4 text-sm text-slate-600">
                {document.form_match.unknown
                  ? "Unknown form. Using dictionary and optional AI guidance."
                  : `Known form: ${document.form_match.display_name}`}
              </p>
              <GuidancePanel
                field={selected}
                guidance={guidance}
                value={selected ? answers[selected.id] ?? "" : ""}
                onChange={(value) => selected && setAnswers((current) => ({ ...current, [selected.id]: value }))}
                onPlay={() => guidance && speech.speak(`${guidance.simple_label}. ${guidance.what_to_enter}`)}
                onStop={speech.stop}
                speaking={speech.speaking}
                available={typeof window !== "undefined" && "speechSynthesis" in window}
                hasLanguageVoice={speech.hasLanguageVoice}
                question={question}
                onQuestion={setQuestion}
                onAsk={async () => {
                  if (!document || !selected) {
                    return;
                  }
                  const result = await askQuestion(document.id, selected.id, question, language, allowAi);
                  setAskAnswer(result.answer);
                }}
                askAnswer={askAnswer}
              />
              <div className="flex flex-wrap gap-2 p-4">
                <button type="button" className="rounded bg-teal-800 px-3 py-2 text-white" onClick={handlePreview}>
                  Create completed reference preview
                </button>
                <button type="button" className="rounded border px-3 py-2" onClick={() => setAnswers({})}>
                  Clear answers
                </button>
                <button type="button" className="rounded border px-3 py-2" onClick={() => setSelectedId(null)}>
                  Clear highlight
                </button>
                <button type="button" className="rounded border px-3 py-2" onClick={reset}>
                  Delete document
                </button>
              </div>
              <div className="lg:hidden">
                <FieldNavigator
                  fields={document.fields}
                  selectedId={selectedId}
                  excluded={excluded}
                  onSelect={setSelectedId}
                  onExclude={(id) => setExcluded(new Set(excluded).add(id))}
                />
              </div>
            </div>
          </div>
        )}
      </main>
      <PreviewDialog preview={preview} onClose={() => setPreview(null)} />
    </div>
  );
}
