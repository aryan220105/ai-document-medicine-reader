import { Minus, Plus } from "lucide-react";
import { FieldOverlay } from "./FieldOverlay";
import { API } from "../api/endpoints";
import type { DetectedField } from "../types";

interface Props {
  documentId: string;
  pageIndex: number;
  pageCount: number;
  fields: DetectedField[];
  selectedId: string | null;
  answers: Record<string, string>;
  zoom: number;
  onZoom: (value: number) => void;
  onSelect: (id: string) => void;
  onPage: (index: number) => void;
}

export function FormViewer({
  documentId,
  pageIndex,
  pageCount,
  fields,
  selectedId,
  answers,
  zoom,
  onZoom,
  onSelect,
  onPage,
}: Props) {
  return (
    <div className="flex h-full min-h-[70vh] flex-col overflow-hidden rounded-3xl border border-softline bg-mist/60 shadow-soft">
      <div className="flex items-center justify-between gap-2 border-b border-softline bg-foam px-3 py-2.5">
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: pageCount }, (_, index) => {
            const count = fields.filter((field) => field.page_index === index).length;
            return (
              <button
                key={index}
                type="button"
                className={`rounded-xl px-3 py-1.5 text-sm font-medium transition ${
                  index === pageIndex ? "bg-leaf text-white" : "bg-white text-ink hover:bg-mist"
                }`}
                onClick={() => onPage(index)}
              >
                Page {index + 1}
                <span className="ml-1 opacity-80">{count === 0 ? "· instructions" : `· ${count}`}</span>
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-1 rounded-xl border border-softline bg-white px-1 py-0.5">
          <button
            type="button"
            aria-label="Zoom out"
            className="rounded-lg p-2 hover:bg-mist"
            onClick={() => onZoom(Math.max(0.6, zoom - 0.1))}
          >
            <Minus className="h-4 w-4" />
          </button>
          <span className="min-w-[3rem] text-center text-sm font-medium">{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            aria-label="Zoom in"
            className="rounded-lg p-2 hover:bg-mist"
            onClick={() => onZoom(Math.min(2.4, zoom + 0.1))}
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
      </div>
      {fields.every((field) => field.page_index !== pageIndex) ? (
        <p className="border-b border-softline bg-amber-50 px-3 py-2 text-sm text-amber-950">
          This page has no fields to fill. Instruction sheets are shown so you can read them, and the answers stay on
          the form page.
        </p>
      ) : null}
      <div className="flex-1 overflow-auto p-4">
        <div className="relative mx-auto origin-top rounded-xl bg-white p-2 shadow-soft" style={{ width: `${zoom * 100}%` }}>
          <img
            src={API.pageProcessed(documentId, pageIndex)}
            alt="Processed form page used as the display surface"
            className="block w-full"
          />
          {fields
            .filter((field) => field.page_index === pageIndex)
            .map((field) => (
              <FieldOverlay
                key={field.id}
                field={field}
                active={selectedId === field.id}
                completed={Boolean(answers[field.id])}
                onSelect={onSelect}
              />
            ))}
        </div>
      </div>
    </div>
  );
}
