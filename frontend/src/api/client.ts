import { API } from "./endpoints";
import type {
  AppConfig,
  DocumentCategory,
  DocumentResponse,
  FieldGuidance,
  Language,
  PreviewResult,
} from "../types";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code = "api_error", status = 400) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function parse(response: Response): Promise<unknown> {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (data as { detail?: { message?: string; code?: string }; message?: string; code?: string }).detail;
    const message = detail?.message || (data as { message?: string }).message || "Something went wrong. Please try again.";
    const code = detail?.code || (data as { code?: string }).code || "request_failed";
    throw new ApiError(message, code, response.status);
  }
  return data;
}

export async function fetchConfig(): Promise<AppConfig> {
  const response = await fetch(API.config);
  return parse(response) as Promise<AppConfig>;
}

export async function uploadDocument(file: File, category: DocumentCategory): Promise<DocumentResponse> {
  const body = new FormData();
  body.append("file", file);
  body.append("category", category);
  const response = await fetch(API.upload, { method: "POST", body });
  return parse(response) as Promise<DocumentResponse>;
}

export async function getDocument(id: string): Promise<DocumentResponse> {
  const response = await fetch(API.status(id));
  return parse(response) as Promise<DocumentResponse>;
}

export async function getFields(id: string): Promise<{ fields: DocumentResponse["fields"] }> {
  const response = await fetch(API.fields(id));
  return parse(response) as Promise<{ fields: DocumentResponse["fields"] }>;
}

export async function requestGuidance(
  id: string,
  fieldId: string,
  language: Language,
  allowExternalAi: boolean,
): Promise<FieldGuidance> {
  const response = await fetch(API.guidance(id), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ field_id: fieldId, language, allow_external_ai: allowExternalAi }),
  });
  return parse(response) as Promise<FieldGuidance>;
}

export async function askQuestion(
  id: string,
  fieldId: string,
  question: string,
  language: Language,
  allowExternalAi: boolean,
): Promise<{ answer: string; source: string; refused: boolean }> {
  const response = await fetch(API.ask(id), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ field_id: fieldId, question, language, allow_external_ai: allowExternalAi }),
  });
  return parse(response) as Promise<{ answer: string; source: string; refused: boolean }>;
}

export async function createPreview(
  id: string,
  answers: { field_id: string; value: string }[],
): Promise<PreviewResult> {
  const response = await fetch(API.preview(id), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  return parse(response) as Promise<PreviewResult>;
}

export async function deleteDocument(id: string): Promise<void> {
  const response = await fetch(API.document(id), { method: "DELETE" });
  await parse(response);
}
