import type { DocumentType } from "../types";
import { DOCUMENT_TYPE_LABELS } from "../utils/validation";

interface Props {
  value: DocumentType;
  onChange: (value: DocumentType) => void;
}

const OPTIONS = Object.keys(DOCUMENT_TYPE_LABELS) as DocumentType[];

export function DocumentTypeSelect({ value, onChange }: Props) {
  return (
    <label className="flex flex-wrap items-center gap-2">
      Detected document type:
      <select
        aria-label="Detected document type"
        className="rounded-full border border-sand bg-white px-3 py-2"
        value={value}
        onChange={(event) => onChange(event.target.value as DocumentType)}
      >
        {OPTIONS.map((option) => (
          <option key={option} value={option}>
            {DOCUMENT_TYPE_LABELS[option]}
          </option>
        ))}
      </select>
    </label>
  );
}
