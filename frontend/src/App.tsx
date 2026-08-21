import { useCallback, useEffect, useMemo, useState } from "react";
import { askDocument, deleteDocument, fetchConfig, getDocument, updateDocumentType, uploadDocument } from "./api/client";
import { ChatPanel } from "./components/ChatPanel";
import { DocumentTypeSelect } from "./components/DocumentTypeSelect";
import { DocumentViewer } from "./components/DocumentViewer";
import { EasyReadToggle } from "./components/EasyReadToggle";
import { LanguageSelector } from "./components/LanguageSelector";
import { OCRPanel } from "./components/OCRPanel";
import { ProcessingProgress } from "./components/ProcessingProgress";
import { StructuredFields } from "./components/StructuredFields";
import { UploadZone } from "./components/UploadZone";
import { useEasyRead } from "./hooks/useEasyRead";
import type { AppConfig, BoundingBox, ChatMessage, DocumentResponse, DocumentType, Language } from "./types";
import { DOCUMENT_SUGGESTIONS, MEDICINE_SUGGESTIONS } from "./utils/validation";

const PRIVACY =
  "Uploaded documents are processed for this demonstration application. Avoid uploading highly sensitive personal information unless the deployment environment is trusted.";

export default function App() {
  const { easyRead, setEasyRead } = useEasyRead();
  const [language, setLanguage] = useState<Language>("en");
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [highlights, setHighlights] = useState<BoundingBox[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchConfig()
      .then(setConfig)
      .catch(() => setConfig(null));
  }, []);

  useEffect(() => {
    if (!document || document.status !== "processing") {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const latest = await getDocument(document.id);
        setDocument(latest);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not refresh document status.");
      }
    }, 600);
    return () => window.clearInterval(timer);
  }, [document]);

  const suggestions = useMemo(() => {
    if (document?.document_type === "medicine_label") {
      return MEDICINE_SUGGESTIONS;
    }
    return DOCUMENT_SUGGESTIONS;
  }, [document?.document_type]);

  const reset = useCallback(async () => {
    if (document) {
      await deleteDocument(document.id);
    }
    if (preview) {
      URL.revokeObjectURL(preview);
    }
    setDocument(null);
    setPreview(null);
    setMessages([]);
    setHighlights([]);
    setError(null);
  }, [document, preview]);

  async function handleFile(file: File) {
    setError(null);
    setMessages([]);
    setHighlights([]);
    if (preview) {
      URL.revokeObjectURL(preview);
    }
    setPreview(URL.createObjectURL(file));
    try {
      const uploaded = await uploadDocument(file);
      setDocument(uploaded);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  async function handleAsk(question: string) {
    if (!document) {
      return;
    }
    setBusy(true);
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", text: question }]);
    try {
      const response = await askDocument(document.id, question, language, easyRead);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "assistant", text: response.answer, response },
      ]);
      if (response.highlights.length) {
        setHighlights(response.highlights);
      }
    } catch (err) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: err instanceof Error ? err.message : "I could not answer that question.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function changeType(value: DocumentType) {
    if (!document) {
      return;
    }
    const updated = await updateDocumentType(document.id, value);
    setDocument(updated);
  }

  const ready = document?.status === "ready";

  return (
    <div className="min-h-screen">
      <header className="border-b border-sand bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-moss">Academic demonstration</p>
            <h1 className="font-serif text-3xl md:text-4xl">AI Document & Medicine Assistant</h1>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <LanguageSelector value={language} onChange={setLanguage} />
            <EasyReadToggle value={easyRead} onChange={setEasyRead} />
            {document ? (
              <button type="button" className="rounded-full border border-clay px-4 py-2 text-clay" onClick={reset}>
                New Document
              </button>
            ) : null}
          </div>
        </div>
      </header>

      {!document ? (
        <div className="mx-auto max-w-5xl px-4 pt-12">
          <p className="max-w-3xl font-serif text-2xl text-slate-700 md:text-3xl">
            Upload a document or medicine label. Ask questions. Understand it in simple language.
          </p>
          <p className="clutter-hide mt-4 max-w-3xl text-slate-600">{config?.privacy_notice ?? PRIVACY}</p>
          {config && !config.llm_configured ? (
            <p className="mt-4 rounded-xl bg-sand px-4 py-3">
              LLM features require an API key. OCR and document extraction remain available.
            </p>
          ) : null}
          {error ? (
            <p role="alert" className="mt-4 text-clay">
              {error}
            </p>
          ) : null}
        </div>
      ) : null}

      {!document ? <UploadZone maxMb={config?.max_upload_mb ?? 10} onFile={handleFile} /> : null}

      {document ? (
        <main className="mx-auto grid max-w-7xl gap-4 px-4 py-6 lg:grid-cols-2">
          <div className="space-y-4">
            {document.status === "processing" ? <ProcessingProgress stage={document.stage} /> : null}
            {document.status === "failed" ? (
              <p role="alert" className="rounded-2xl bg-red-50 p-4 text-clay">
                {document.error_message || "Processing failed. Try a clearer photo."}
              </p>
            ) : null}
            <DocumentViewer
              originalUrl={preview ?? document.original_image_url}
              processedUrl={document.processed_image_url}
              highlights={highlights}
              preferProcessed={Boolean(document.processed_image_url)}
            />
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white p-4">
              <DocumentTypeSelect value={document.document_type} onChange={changeType} />
              <button type="button" className="rounded-full border px-4 py-2" onClick={() => setHighlights([])}>
                Clear Highlights
              </button>
            </div>
            {preview ? (
              <div className="flex gap-2">
                <label className="rounded-full border px-4 py-2">
                  Replace image
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    className="sr-only"
                    aria-label="Replace image"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) {
                        void handleFile(file);
                      }
                    }}
                  />
                </label>
                <button type="button" className="rounded-full border px-4 py-2" onClick={reset}>
                  Remove image
                </button>
              </div>
            ) : null}
          </div>
          <div className="space-y-4">
            <ChatPanel
              messages={messages}
              suggestions={ready ? suggestions : []}
              busy={busy || !ready}
              onAsk={handleAsk}
              onExplainSimply={() => handleAsk("Explain this simply.")}
            />
            <StructuredFields fields={document.fields} />
          </div>
          <div className="lg:col-span-2">
            <OCRPanel
              text={document.ocr_text}
              confidence={document.average_confidence}
              level={document.confidence_level}
            />
          </div>
          {error ? (
            <p role="alert" className="lg:col-span-2 text-clay">
              {error}
            </p>
          ) : null}
        </main>
      ) : null}
    </div>
  );
}
