import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { overlayStyle, validateAnswer, validateUpload } from "../utils/validation";
import { SourceBadge } from "../components/SourceBadge";
import { ProcessingProgress } from "../components/ProcessingProgress";
import { FieldOverlay } from "../components/FieldOverlay";
import { FieldNavigator } from "../components/FieldNavigator";
import { VoiceButton } from "../components/VoiceButton";
import type { DetectedField } from "../types";

const field: DetectedField = {
  id: "p0-f0",
  page_index: 0,
  label: "Full Name",
  field_type: "text",
  input_box: { x: 0.2, y: 0.3, width: 0.4, height: 0.05, page_index: 0 },
  label_boxes: [],
  source_word_ids: [],
  options: [],
  required: true,
  confidence: 0.4,
  confidence_reasons: ["low"],
};

vi.mock("../api/client", () => ({
  ApiError: class ApiError extends Error {
    code = "x";
    status = 400;
  },
  fetchConfig: vi.fn(async () => ({
    llm_configured: false,
    external_ai_enabled: false,
    max_upload_mb: 10,
    max_pdf_pages: 5,
    languages: ["en", "hi", "kn"],
    categories: ["banking"],
    accepted_types: ["image/png"],
    privacy_notice: "Academic demonstration privacy notice.",
  })),
  uploadDocument: vi.fn(async () => ({
    id: "doc-1",
    original_filename: "form.png",
    status: "ready",
    stage: "ready",
    category: "banking",
    page_count: 1,
    fields: [
      {
        id: "p0-f0",
        page_index: 0,
        label: "Full Name",
        field_type: "text",
        input_box: { x: 0.2, y: 0.3, width: 0.4, height: 0.05, page_index: 0 },
        label_boxes: [],
        source_word_ids: [],
        options: [],
        required: true,
        confidence: 0.9,
        confidence_reasons: [],
      },
    ],
    form_match: { form_id: "demo_bank_account_opening_v1", display_name: "Demo Bank", category: "banking", score: 0.9, matched_terms: [], unknown: false },
    error_message: null,
    llm_configured: false,
    created_at: new Date().toISOString(),
  })),
  getDocument: vi.fn(),
  getFields: vi.fn(async () => ({ fields: [] })),
  requestGuidance: vi.fn(async () => ({
    field_id: "p0-f0",
    language: "en",
    simple_label: "Full name",
    what_to_enter: "Enter your full legal name.",
    why_needed: null,
    example: "Ananya Rao",
    format_hint: null,
    source: "known_form_knowledge_base",
    source_reference: "demo",
    confidence: 0.93,
    requires_verification: false,
    highlights: [],
  })),
  askQuestion: vi.fn(),
  createPreview: vi.fn(async () => ({ preview_id: "p1", pdf_url: "/api/documents/doc-1/previews/p1.pdf", warnings: [] })),
  deleteDocument: vi.fn(async () => undefined),
}));

describe("upload and preferences", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders upload, category, language, and privacy controls", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: "FormSathi" })).toBeInTheDocument();
    expect(screen.getByText(/Drop a PNG/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Form category/)).toBeInTheDocument();
    expect(screen.getAllByLabelText(/Answer language/).length).toBeGreaterThan(0);
    expect(screen.getByTestId("privacy-notice")).toBeInTheDocument();
    expect(screen.getByText(/Allow external AI/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Allow external AI/ })).toBeDisabled();
  });

  it("validates files locally", () => {
    expect(validateUpload(new File(["x"], "a.txt", { type: "text/plain" }))).toMatch(/PNG/);
    const big = new File([new Uint8Array(11 * 1024 * 1024)], "a.png", { type: "image/png" });
    expect(validateUpload(big)).toMatch(/10 MB/);
  });

  it("persists Easy Read", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByLabelText("Easy Read"));
    expect(localStorage.getItem("formsathi.easyRead")).toBe("true");
  });
});

describe("workspace widgets", () => {
  it("shows processing stages", () => {
    render(<ProcessingProgress stage="reading_text" />);
    expect(screen.getByText("Reading printed text")).toBeInTheDocument();
    expect(screen.getByText("Detecting fields")).toBeInTheDocument();
  });

  it("positions overlays from normalized coordinates", () => {
    const style = overlayStyle({ x: 0.2, y: 0.3, width: 0.4, height: 0.05 });
    expect(style.left).toBe("20%");
    expect(style.top).toBe("30%");
    expect(style.width).toBe("40%");
    expect(style.height).toBe("5%");
  });

  it("selects a field from the overlay and navigator", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const { rerender } = render(
      <div className="relative h-40 w-40">
        <FieldOverlay field={field} active={false} completed={false} onSelect={onSelect} />
      </div>,
    );
    await user.click(screen.getByLabelText("Full Name"));
    expect(onSelect).toHaveBeenCalledWith("p0-f0");
    rerender(<FieldNavigator fields={[field]} selectedId={null} excluded={new Set()} onSelect={onSelect} onExclude={vi.fn()} />);
    await user.click(screen.getByText("Full Name"));
    expect(onSelect).toHaveBeenCalledTimes(2);
  });

  it("shows source badge and low-confidence warning", () => {
    render(<SourceBadge source="known_form_knowledge_base" />);
    expect(screen.getByTestId("source-badge")).toHaveTextContent("Known Form Knowledge Base");
    render(<FieldNavigator fields={[field]} selectedId={null} excluded={new Set()} onSelect={vi.fn()} onExclude={vi.fn()} />);
    expect(screen.getByText("Low confidence")).toBeInTheDocument();
  });

  it("validates dates", () => {
    expect(validateAnswer({ ...field, field_type: "date", confidence: 0.9 }, "99")).toMatch(/date/i);
    expect(validateAnswer({ ...field, field_type: "date", confidence: 0.9 }, "15/08/1998")).toBeNull();
  });

  it("shows voice fallback", () => {
    render(<VoiceButton onPlay={vi.fn()} onStop={vi.fn()} speaking={false} available={false} hasLanguageVoice={false} />);
    expect(screen.getByText(/Voice is not available/)).toBeInTheDocument();
  });
});

describe("preview and reset", () => {
  it("requests a preview and can start a new form", async () => {
    const user = userEvent.setup();
    const { uploadDocument } = await import("../api/client");
    render(<App />);
    const file = new File(["png"], "form.png", { type: "image/png" });
    const input = (await screen.findByText("Choose file")).parentElement?.querySelector("input") as HTMLInputElement;
    await user.upload(input, file);
    await waitFor(() => expect(uploadDocument).toHaveBeenCalled());
    await user.click(await screen.findByText("Create completed reference preview"));
    expect(await screen.findByText("Completed Reference Preview")).toBeInTheDocument();
    expect(screen.getByText("Download PDF")).toBeInTheDocument();
    await user.click(screen.getByText("Start new form"));
    expect(await screen.findByText(/Drop a PNG/)).toBeInTheDocument();
  });

  it("renders friendly API errors", async () => {
    const { fetchConfig, ApiError } = await import("../api/client");
    vi.mocked(fetchConfig).mockReset();
    vi.mocked(fetchConfig).mockRejectedValue(new ApiError("The assistance service is unavailable.", "down", 503));
    render(<App />);
    expect((await screen.findAllByRole("alert"))[0]).toHaveTextContent("unavailable");
  });
});
