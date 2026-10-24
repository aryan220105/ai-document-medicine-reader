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
    <div className="flex h-full min-h-[70vh] flex-col overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 py-2">
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: pageCount }, (_, index) => {
            const count = fields.filter((field) => field.page_index === index).length;
            return (
              <button
                key={index}
                type="button"
                className={`rounded-md px-3 py-1.5 text-sm ${index === pageIndex ? "bg-teal-800 text-white" : "bg-slate-100 text-slate-800"}`}
                onClick={() => onPage(index)}
              >
                Page {index + 1}
                <span className="ml-1 opacity-80">{count === 0 ? "· instructions" : `· ${count}`}</span>
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          <button type="button" aria-label="Zoom out" onClick={() => onZoom(Math.max(0.6, zoom - 0.1))}>
            <Minus className="h-4 w-4" />
          </button>
          <span className="text-sm">{Math.round(zoom * 100)}%</span>
          <button type="button" aria-label="Zoom in" onClick={() => onZoom(Math.min(2.4, zoom + 0.1))}>
            <Plus className="h-4 w-4" />
          </button>
        </div>
      </div>
      {fields.every((field) => field.page_index !== pageIndex) ? (
        <p className="border-b border-slate-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          This page has no fields to fill. Instruction sheets are shown so you can read them, and the answers stay on the form page.
        </p>
      ) : null}
      <div className="flex-1 overflow-auto p-4">
        <div className="relative mx-auto origin-top" style={{ width: `${zoom * 100}%` }}>
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
