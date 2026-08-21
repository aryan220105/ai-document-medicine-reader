import type { AppConfig, ChatResponse, DocumentResponse, DocumentType, Language } from "../types";

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    /* ignore */
  }
  return "Something went wrong. Please try again.";
}

export async function fetchConfig(): Promise<AppConfig> {
  const response = await fetch("/api/config");
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json() as Promise<AppConfig>;
}

export async function uploadDocument(file: File): Promise<DocumentResponse> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/documents/upload", { method: "POST", body });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json() as Promise<DocumentResponse>;
}

export async function getDocument(id: string): Promise<DocumentResponse> {
  const response = await fetch(`/api/documents/${id}`);
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json() as Promise<DocumentResponse>;
}

export async function askDocument(
  id: string,
  question: string,
  language: Language,
  easyRead: boolean,
): Promise<ChatResponse> {
  const response = await fetch(`/api/documents/${id}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, language, easy_read: easyRead }),
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json() as Promise<ChatResponse>;
}

export async function deleteDocument(id: string): Promise<void> {
  await fetch(`/api/documents/${id}`, { method: "DELETE" });
}

export async function updateDocumentType(id: string, documentType: DocumentType): Promise<DocumentResponse> {
  const response = await fetch(`/api/documents/${id}/type`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_type: documentType }),
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json() as Promise<DocumentResponse>;
}
