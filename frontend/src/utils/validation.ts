const ALLOWED = ["image/png", "image/jpeg", "image/webp", "image/jpg"];

export function validateImageFile(file: File, maxMb = 10): string | null {
  const type = file.type.toLowerCase();
  if (!ALLOWED.includes(type) && !/\.(png|jpe?g|webp)$/i.test(file.name)) {
    return "Please upload a PNG, JPG, JPEG, or WEBP image.";
  }
  if (file.size > maxMb * 1024 * 1024) {
    return `Please upload an image smaller than ${maxMb} MB.`;
  }
  if (file.size === 0) {
    return "The selected file is empty.";
  }
  return null;
}

export const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  medicine_label: "Medicine Label",
  electricity_bill: "Electricity Bill",
  bank_document: "Bank Document",
  insurance_document: "Insurance Document",
  government_notice: "Government Notice",
  tax_document: "Tax Document",
  general_document: "General Document",
  unknown: "Unknown",
};

export const STAGE_LABELS: Record<string, string> = {
  uploading: "Uploading image",
  detecting: "Detecting document",
  enhancing: "Enhancing image",
  ocr: "Running OCR",
  extracting: "Extracting important information",
  indexing: "Building searchable document context",
  ready: "Ready",
  failed: "Processing failed",
};

export const MEDICINE_SUGGESTIONS = [
  "What is the medicine name?",
  "What is the expiry date?",
  "What dosage is printed?",
  "Are there any warnings?",
  "Explain this label simply.",
  "Are there any food-related precautions?",
  "Where is the expiry date?",
];

export const DOCUMENT_SUGGESTIONS = [
  "Summarize this document.",
  "What do I need to do?",
  "Is there a due date?",
  "How much do I need to pay?",
  "What is the account/reference number?",
  "Are there any important deadlines?",
  "Where is the due date?",
];
