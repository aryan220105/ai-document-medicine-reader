import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  askQuestion,
  createPreview,
  deleteDocument,
  fetchConfig,
  fetchGuidanceBundle,
  getDocument,
  getFields,
  uploadDocument,
} from "./api/client";
import { FieldNavigator } from "./components/FieldNavigator";
import { FormContextNote } from "./components/FormContextNote";
import { FormViewer } from "./components/FormViewer";
import { GuidancePanel } from "./components/GuidancePanel";
import { LanguageSelector } from "./components/LanguageSelector";
import { PreviewDialog } from "./components/PreviewDialog";
import { ProcessingProgress } from "./components/ProcessingProgress";
import { UploadZone } from "./components/UploadZone";
import { useEasyRead } from "./hooks/useEasyRead";
import { useSpeech } from "./hooks/useSpeech";
import type {
  AppConfig,
  DocumentCategory,
  DocumentResponse,
  Language,
  MultilingualFieldGuidance,
  PreviewResult,
} from "./types";
import { isSupported, nativeNameFor, scriptLabel, textForSpeech } from "./utils/languages";
import { validateUpload } from "./utils/validation";

const LANGUAGE_KEY = "formsathi.language";
/** How many times to retry the first config call while the backend is still starting. */
const CONFIG_RETRIES = 5;

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const storedLanguage = typeof localStorage === "undefined" ? null : localStorage.getItem(LANGUAGE_KEY);
  const [language, setLanguage] = useState<Language>(isSupported(storedLanguage) ? storedLanguage : "en");
  // True once the user has picked a language themselves. After that the form's detected
  // script never overrides their choice.
  const languageChosen = useRef(isSupported(storedLanguage));
  const [category, setCategory] = useState<DocumentCategory>("other");
  const [allowAi, setAllowAi] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [bundles, setBundles] = useState<Record<string, MultilingualFieldGuidance>>({});
  const [bundleLoading, setBundleLoading] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [pageIndex, setPageIndex] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [question, setQuestion] = useState("");
  const [askAnswer, setAskAnswer] = useState("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const { easyRead, setEasyRead } = useEasyRead();
  const speech = useSpeech(language, Boolean(config?.speech_configured));

  useEffect(() => {
    let cancelled = false;
    // The very first request is the one that fails when the backend has not finished
    // starting, so it gets a message that says what to do instead of the generic
    // "something went wrong" the API client falls back to.
    const load = (attempt: number) => {
      fetchConfig()
        .then((value) => {
          if (!cancelled) {
            setConfig(value);
            setError(null);
          }
        })
        .catch(() => {
          if (cancelled) {
            return;
          }
          if (attempt < CONFIG_RETRIES) {
            // The backend loads an embedding model before it binds its port, so a cold
            // start can take a while. Keep trying quietly before blaming anything.
            setError(null);
            window.setTimeout(() => load(attempt + 1), 2000);
            return;
          }
          setError(
            "Cannot reach the FormSathi backend on port 8000. Start it with " +
              "`uvicorn app.main:app --reload --port 8000` from the backend folder, then reload this page. " +
              "A first start can take a minute while the embedding model loads.",
          );
        });
    };
    load(0);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    localStorage.setItem(LANGUAGE_KEY, language);
  }, [language]);

  const chooseLanguage = useCallback((next: Language) => {
    languageChosen.current = true;
    setLanguage(next);
    // Deliberately nothing else: the document, its pages, and `answers` are untouched,
    // so switching explanation language cannot alter the form or lose typed work.
  }, []);

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

  // Select the first field as soon as the form is ready. Upload can return a ready
  // document straight away, in which case the polling effect above never runs and the
  // guidance panel would otherwise sit empty with every field already detected.
  useEffect(() => {
    if (!document || document.status !== "ready" || selectedId) {
      return;
    }
    const first = document.fields[0];
    if (first) {
      setSelectedId(first.id);
      setPageIndex(first.page_index);
    }
  }, [document?.id, document?.status, document?.fields, selectedId]);

  // Open an unknown regional-script form in the language its labels are printed in, but
  // only until the user expresses a preference of their own.
  useEffect(() => {
    if (!document || document.status !== "ready" || languageChosen.current) {
      return;
    }
    if (isSupported(document.suggested_language) && document.suggested_language !== language) {
      setLanguage(document.suggested_language);
    }
  }, [document?.id, document?.status, document?.suggested_language]);

  // One request covers every field in every language. Re-run only when the document
  // changes or the user changes their consent to use the optional AI -- never on a
  // language switch, which is a local lookup.
  useEffect(() => {
    if (!document || document.status !== "ready" || document.fields.length === 0) {
      return;
    }
    let cancelled = false;
    setBundleLoading(true);
    fetchGuidanceBundle(document.id, { allowExternalAi: allowAi })
      .then((response) => {
        if (cancelled) {
          return;
        }
        const next: Record<string, MultilingualFieldGuidance> = {};
        for (const item of response.bundles) {
          next[item.field_id] = item;
        }
        setBundles(next);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Guidance could not be loaded.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setBundleLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [document?.id, document?.status, document?.fields.length, allowAi]);

  const selected = useMemo(
    () => document?.fields.find((field) => field.id === selectedId) ?? null,
    [document, selectedId],
  );

  const bundle = selectedId ? bundles[selectedId] ?? null : null;
  // The language switch is this lookup, and nothing more.
  const guidance = bundle ? bundle.languages[language] ?? bundle.languages.en ?? null : null;

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
      setBundles({});
      setExcluded(new Set());
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
    setBundles({});
    setAnswers({});
    setError(null);
    setPreview(null);
  }

  async function handlePreview() {
    if (!document) {
      return;
    }
    const payload = Object.entries(answers)
      .filter(([fieldId]) => !excluded.has(fieldId))
      .map(([field_id, value]) => ({ field_id, value }));
    try {
      setPreview(await createPreview(document.id, payload, language));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Preview could not be created.");
    }
  }

  const unknownForm = document?.form_match.unknown ?? false;
  const resolvedCount = document?.fields.filter((field) => field.semantic_id).length ?? 0;
  // A response from an older build, or a cached one, may not carry these yet.
  const scripts = document?.scripts ?? [];

  return (
    <div className={`min-h-screen ${easyRead ? "easy-read" : ""}`}>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3 shadow-sm">
        <div>
          <p className="font-serif text-xl text-slate-900">FormSathi</p>
          <p className="text-sm text-slate-600">English, Hindi, Kannada, and Urdu guidance for the form in front of you</p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <LanguageSelector value={language} onChange={chooseLanguage} compact />
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
        {error ? (
          <p role="alert" className="mb-4 rounded bg-red-50 p-3 text-red-900">
            {error}
          </p>
        ) : null}
        {!document ? (
          <UploadZone
            config={config}
            language={language}
            onLanguage={chooseLanguage}
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
          <div className="grid items-start gap-4 lg:grid-cols-[240px_minmax(0,1fr)_360px]">
            <div className="hidden rounded-xl border border-slate-200 bg-white p-3 lg:block">
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
            <div className="rounded-xl border border-slate-200 bg-white">
              <div className="px-4 text-sm text-slate-600" data-testid="form-status">
                {unknownForm ? (
                  <p>
                    Unknown form. {resolvedCount} of {document.fields.length} fields matched the multilingual field
                    dictionary; the rest are described from their printed wording.
                  </p>
                ) : (
                  <p>Known form: {document.form_match.display_name}</p>
                )}
                {scripts.length > 0 ? (
                  <p className="mt-1 text-xs">
                    Printed script: {scripts.map(scriptLabel).join(", ")}. Explanations shown in{" "}
                    {nativeNameFor(language)}; the form itself is never translated.
                  </p>
                ) : null}
                {document.interpreter_used ? (
                  <p className="mt-1 text-xs" data-testid="interpreter-note">
                    Fields were read in the context of their column headings, so repeated labels on this
                    form are told apart.
                  </p>
                ) : config?.interpreter_enabled === false ? (
                  <p className="mt-1 text-xs" data-testid="interpreter-off">
                    Context reading is off, so fields are matched by their printed wording alone. Dense
                    tables with repeated labels may be described imprecisely.
                  </p>
                ) : null}
                {bundleLoading ? <p className="mt-1 text-xs">Preparing guidance in all languages…</p> : null}
                <FormContextNote context={document.form_context} />
              </div>
              <GuidancePanel
                field={selected}
                guidance={guidance}
                bundle={bundle}
                language={language}
                onLanguage={chooseLanguage}
                value={selected ? answers[selected.id] ?? "" : ""}
                onChange={(value) => selected && setAnswers((current) => ({ ...current, [selected.id]: value }))}
                onPlay={() =>
                  guidance && speech.speak(textForSpeech(guidance.simple_label, guidance.what_to_enter, language))
                }
                onStop={speech.stop}
                speaking={speech.speaking}
                loading={speech.loading}
                error={speech.error}
                provider={speech.provider}
                configured={Boolean(config?.speech_configured)}
                available={speech.available}
                hasLanguageVoice={speech.hasLanguageVoice}
                canSpeak={speech.canSpeak}
                voiceLanguage={speech.voiceLanguage}
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
