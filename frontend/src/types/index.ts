export type Language = "en" | "hi" | "kn";
export type DocumentCategory = "government" | "banking" | "insurance" | "education" | "financial" | "other";
export type DocumentStatus = "processing" | "ready" | "failed";
export type ProcessingStage =
  | "validating"
  | "preparing_pages"
  | "reading_text"
  | "detecting_fields"
  | "matching_form"
  | "ready"
  | "failed";
export type FieldType = "text" | "multiline" | "date" | "checkbox" | "radio" | "signature" | "table_cell";
export type GuidanceSource =
  | "known_form_knowledge_base"
  | "common_field_dictionary"
  | "printed_form_text"
  | "general_ai_guidance"
  | "unavailable";

export interface NormalizedBoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  page_index: number;
  label?: string | null;
}

export interface DetectedField {
  id: string;
  page_index: number;
  label: string;
  field_type: FieldType;
  input_box: NormalizedBoundingBox;
  label_boxes: NormalizedBoundingBox[];
  source_word_ids: string[];
  options: { id: string; label: string; box: NormalizedBoundingBox }[];
  required: boolean | null;
  confidence: number;
  confidence_reasons: string[];
}

export interface KnownFormMatch {
  form_id: string | null;
  display_name: string | null;
  category: DocumentCategory | null;
  score: number;
  matched_terms: string[];
  unknown: boolean;
}

export interface DocumentResponse {
  id: string;
  original_filename: string;
  status: DocumentStatus;
  stage: ProcessingStage;
  category: DocumentCategory;
  page_count: number;
  fields: DetectedField[];
  form_match: KnownFormMatch;
  error_message: string | null;
  llm_configured: boolean;
  created_at: string;
}

export interface FieldGuidance {
  field_id: string;
  language: Language;
  simple_label: string;
  what_to_enter: string;
  why_needed: string | null;
  example: string | null;
  format_hint: string | null;
  source: GuidanceSource;
  source_reference: string | null;
  confidence: number;
  requires_verification: boolean;
  highlights: NormalizedBoundingBox[];
}

export interface AppConfig {
  llm_configured: boolean;
  external_ai_enabled: boolean;
  max_upload_mb: number;
  max_pdf_pages: number;
  languages: Language[];
  categories: DocumentCategory[];
  accepted_types: string[];
  privacy_notice: string;
}

export interface ApiErrorBody {
  code?: string;
  message?: string;
  details?: Record<string, string>;
}

export interface PreviewResult {
  preview_id: string;
  pdf_url: string;
  warnings: { field_id: string; code: string; message: string }[];
}

export const STAGE_LABELS: Record<ProcessingStage, string> = {
  validating: "Validating file",
  preparing_pages: "Preparing pages",
  reading_text: "Reading printed text",
  detecting_fields: "Detecting fields",
  matching_form: "Checking known-form guidance",
  ready: "Preparing assistance",
  failed: "Processing failed",
};
