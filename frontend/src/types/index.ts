export type Language = "en" | "hi" | "kn";

export type DocumentType =
  | "medicine_label"
  | "electricity_bill"
  | "bank_document"
  | "insurance_document"
  | "government_notice"
  | "tax_document"
  | "general_document"
  | "unknown";

export type ProcessingStage =
  | "uploading"
  | "detecting"
  | "enhancing"
  | "ocr"
  | "extracting"
  | "indexing"
  | "ready"
  | "failed";

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  label?: string | null;
}

export interface DetectedField {
  field_type: string;
  value: string;
  confidence: number;
  word_ids: number[];
  bounding_boxes: BoundingBox[];
  uncertain: boolean;
  label?: string | null;
}

export interface DocumentResponse {
  id: string;
  original_filename: string;
  status: "processing" | "ready" | "failed";
  stage: ProcessingStage;
  document_type: DocumentType;
  detection_succeeded: boolean;
  average_confidence: number;
  confidence_level: string;
  ocr_text: string;
  fields: DetectedField[];
  error_message?: string | null;
  original_image_url: string;
  processed_image_url?: string | null;
  llm_configured: boolean;
  created_at: string;
}

export interface ChatResponse {
  answer: string;
  document_sources: string[];
  knowledge_sources: string[];
  highlights: BoundingBox[];
  confidence: number;
  intent: string;
  llm_used: boolean;
  llm_unavailable: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: ChatResponse;
}

export interface AppConfig {
  llm_configured: boolean;
  max_upload_mb: number;
  languages: Language[];
  accepted_types: string[];
  privacy_notice: string;
}
