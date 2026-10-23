export type Language = "en" | "hi" | "kn" | "ur";
export type TextDirection = "ltr" | "rtl";
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
  | "label_pattern_heuristic"
  | "page_interpretation"
  | "general_ai_guidance"
  | "unavailable";

export interface ValidationRule {
  kind: string;
  pattern: string | null;
  message: string | null;
  format: string | null;
  optional: boolean;
  min_value: number | null;
  max_value: number | null;
  max_length: number | null;
}

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
  known_field_id?: string | null;
  semantic_id?: string | null;
  semantic_score?: number;
  semantic_source?: string | null;
  label_pattern_id?: string | null;
  validation_rule?: ValidationRule | null;
  label_script?: string | null;
  label_language?: Language | null;
  /** Disambiguated name worked out by reading the page, e.g. "AC Name (Relative)". */
  display_label?: string;
  /** "applicant" | "office" | "either" — who the form expects to fill this in. */
  filled_by?: string;
  caption?: string;
  column_header?: string;
  sub_header?: string;
  section_hint?: string;
  structure_origin?: string;
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
  scripts: string[];
  suggested_language: Language;
  interpreter_used?: boolean;
  form_context?: FormContext | null;
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
  validation_rule: ValidationRule | null;
  confidence: number;
  requires_verification: boolean;
  highlights: NormalizedBoundingBox[];
  inferred: boolean;
  verify_notice: string | null;
}

/** Guidance for one field in every supported language at once. */
export interface MultilingualFieldGuidance {
  field_id: string;
  semantic_id: string | null;
  label_language: Language | null;
  source: GuidanceSource;
  confidence: number;
  requires_verification: boolean;
  inferred: boolean;
  languages: Partial<Record<Language, FieldGuidance>>;
}

export interface GuidanceBundleResponse {
  document_id: string;
  bundles: MultilingualFieldGuidance[];
  languages: Language[];
  llm_used: boolean;
}

/** What the document turned out to be, read once before any field was described. */
export interface FormContext {
  title: string;
  authority: string;
  purpose: string;
  glossary: Record<string, string>;
  notes: string[];
  office_sections: string[];
  /** Where any web-sourced background came from. Empty when none was used. */
  web_sources?: string[];
  confidence: number;
}

export interface ValidationResult {
  ok: boolean;
  message: string | null;
}

export interface LanguageDetail {
  id: Language;
  label: string;
  native: string;
  locale: string;
  direction: TextDirection;
}

export interface AppConfig {
  llm_configured: boolean;
  external_ai_enabled: boolean;
  max_upload_mb: number;
  max_pdf_pages: number;
  languages: Language[];
  language_details: LanguageDetail[];
  categories: DocumentCategory[];
  accepted_types: string[];
  dictionary_fields: number;
  interpreter_enabled?: boolean;
  label_patterns: number;
  ocr_languages: string;
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
