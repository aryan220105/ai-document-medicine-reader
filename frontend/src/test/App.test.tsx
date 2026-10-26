import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { foldDigits, overlayStyle, validateAnswer, validateUpload } from "../utils/validation";
import { SourceBadge } from "../components/SourceBadge";
import { ProcessingProgress } from "../components/ProcessingProgress";
import { FieldOverlay } from "../components/FieldOverlay";
import { FieldNavigator } from "../components/FieldNavigator";
import { VoiceButton } from "../components/VoiceButton";
import { DirectionalText } from "../components/DirectionalText";
import { FieldInput } from "../components/FieldInput";
import { directionFor, isSupported, LANGUAGE_IDS } from "../utils/languages";
import type { DetectedField, MultilingualFieldGuidance } from "../types";

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

/** An Urdu field on an unknown form, resolved through the multilingual dictionary. */
const urduField: DetectedField = {
  id: "p0-f1",
  page_index: 0,
  label: "والد کا نام",
  field_type: "text",
  input_box: { x: 0.2, y: 0.4, width: 0.4, height: 0.05, page_index: 0 },
  label_boxes: [],
  source_word_ids: [],
  options: [],
  required: true,
  confidence: 0.82,
  confidence_reasons: [],
  semantic_id: "father_name",
  semantic_score: 1,
  semantic_source: "exact",
  label_script: "arabic",
  label_language: "ur",
  validation_rule: {
    kind: "person_name",
    pattern: null,
    message: null,
    format: null,
    optional: false,
    min_value: null,
    max_value: null,
    max_length: 80,
  },
};

const GUIDANCE_TEXT = {
  en: "Write your father's full name as it appears on your own identity records.",
  hi: "अपने पिता का पूरा नाम अपने पहचान अभिलेख के अनुसार लिखें।",
  kn: "ನಿಮ್ಮ ಗುರುತಿನ ದಾಖಲೆಗಳಲ್ಲಿ ಇರುವಂತೆ ನಿಮ್ಮ ತಂದೆಯ ಪೂರ್ಣ ಹೆಸರನ್ನು ಬರೆಯಿರಿ.",
  ur: "اپنے والد کا پورا نام اپنی شناختی دستاویز کے مطابق لکھیں۔",
} as const;

function bundleFor(fieldId: string): MultilingualFieldGuidance {
  const languages = Object.fromEntries(
    (Object.keys(GUIDANCE_TEXT) as (keyof typeof GUIDANCE_TEXT)[]).map((code) => [
      code,
      {
        field_id: fieldId,
        language: code,
        simple_label: code === "ur" ? "والد کا نام" : "Father's name",
        what_to_enter: GUIDANCE_TEXT[code],
        why_needed: null,
        example: "Mahesh Rao",
        format_hint: null,
        validation_rule: null,
        source: "common_field_dictionary" as const,
        source_reference: "father_name",
        confidence: 0.92,
        requires_verification: false,
        highlights: [],
        inferred: false,
        verify_notice: null,
      },
    ]),
  );
  return {
    field_id: fieldId,
    semantic_id: "father_name",
    label_language: "ur",
    source: "common_field_dictionary",
    confidence: 0.92,
    requires_verification: false,
    inferred: false,
    languages,
  };
}

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
    languages: ["en", "hi", "kn", "ur"],
    language_details: [],
    categories: ["banking"],
    accepted_types: ["image/png"],
    dictionary_fields: 56,
    label_patterns: 7,
    ocr_languages: "eng+hin+kan+urd",
    privacy_notice: "Academic demonstration privacy notice.",
  })),
  uploadDocument: vi.fn(async () => ({
    id: "doc-1",
    original_filename: "form.png",
    status: "ready",
    stage: "ready",
    category: "banking",
    page_count: 1,
    fields: [urduField],
    form_match: {
      form_id: null,
      display_name: null,
      category: null,
      score: 0.1,
      matched_terms: [],
      unknown: true,
    },
    scripts: ["arabic"],
    suggested_language: "ur",
    error_message: null,
    llm_configured: false,
    created_at: new Date().toISOString(),
  })),
  getDocument: vi.fn(),
  getFields: vi.fn(async () => ({ fields: [] })),
  fetchGuidanceBundle: vi.fn(async () => ({
    document_id: "doc-1",
    bundles: [bundleFor("p0-f1")],
    languages: ["en", "hi", "kn", "ur"],
    llm_used: false,
  })),
  requestGuidance: vi.fn(),
  validateAnswerRemote: vi.fn(async () => ({ ok: true, message: null })),
  askQuestion: vi.fn(),
  createPreview: vi.fn(async () => ({
    preview_id: "p1",
    pdf_url: "/api/documents/doc-1/previews/p1.pdf",
    warnings: [],
  })),
  deleteDocument: vi.fn(async () => undefined),
}));

async function uploadAndWait(user: ReturnType<typeof userEvent.setup>) {
  const { uploadDocument } = await import("../api/client");
  const file = new File(["png"], "form.png", { type: "image/png" });
  const input = (await screen.findByText("Choose file")).parentElement?.querySelector(
    "input",
  ) as HTMLInputElement;
  await user.upload(input, file);
  await waitFor(() => expect(uploadDocument).toHaveBeenCalled());
  return screen.findByTestId("guidance-body");
}

describe("upload and preferences", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("renders upload, category, language, and privacy controls", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: "FormSathi" })).toBeInTheDocument();
    expect(screen.getByText(/Drop a PNG/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Form category/)).toBeInTheDocument();
    expect(screen.getAllByLabelText(/Explanation language/).length).toBeGreaterThan(0);
    expect(screen.getByTestId("privacy-notice")).toBeInTheDocument();
    expect(screen.getByText(/Allow external AI/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Allow external AI/ })).toBeDisabled();
  });

  it("offers all four explanation languages, Urdu included", async () => {
    render(<App />);
    const select = (await screen.findAllByLabelText(/Explanation language/))[0] as HTMLSelectElement;
    const values = Array.from(select.options).map((option) => option.value);
    expect(values).toEqual(["en", "hi", "kn", "ur"]);
    expect(LANGUAGE_IDS).toContain("ur");
    expect(isSupported("ur")).toBe(true);
    expect(isSupported("fr")).toBe(false);
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

describe("unknown-form flow", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("reports an unknown form and how many fields the dictionary resolved", async () => {
    const user = userEvent.setup();
    render(<App />);
    await uploadAndWait(user);
    const status = screen.getByTestId("form-status");
    expect(status).toHaveTextContent(/Unknown form/);
    expect(status).toHaveTextContent(/1 of 1 fields matched/);
    expect(status).toHaveTextContent(/Arabic \/ Urdu/);
    expect(status).toHaveTextContent(/never translated/);
  });

  it("fetches every language in one request, not one request per language", async () => {
    const user = userEvent.setup();
    const { fetchGuidanceBundle } = await import("../api/client");
    render(<App />);
    await uploadAndWait(user);
    await waitFor(() => expect(fetchGuidanceBundle).toHaveBeenCalledTimes(1));

    const select = screen.getAllByLabelText(/Explanation language/)[1] as HTMLSelectElement;
    await user.selectOptions(select, "hi");
    await user.selectOptions(select, "kn");
    await user.selectOptions(select, "en");
    // Switching language is a local lookup: no further network calls.
    expect(fetchGuidanceBundle).toHaveBeenCalledTimes(1);
  });

  it("opens an Urdu form in Urdu and renders the guidance right-to-left", async () => {
    const user = userEvent.setup();
    render(<App />);
    const body = await uploadAndWait(user);
    expect(body).toHaveAttribute("data-language", "ur");
    const paragraph = within(body).getByText(GUIDANCE_TEXT.ur);
    expect(paragraph).toHaveAttribute("dir", "rtl");
    expect(directionFor("ur")).toBe("rtl");
  });

  it("switches the description language without changing the form or the typed answer", async () => {
    const user = userEvent.setup();
    render(<App />);
    const body = await uploadAndWait(user);

    // The printed label is the form's content. It keeps its own script and direction
    // whatever the explanation language is.
    const heading = screen.getByRole("heading", { name: urduField.label });
    expect(heading).toHaveAttribute("dir", "rtl");

    const answerBox = screen.getByLabelText("Your answer") as HTMLInputElement;
    await user.type(answerBox, "Mahesh Rao");
    expect(answerBox.value).toBe("Mahesh Rao");

    const select = screen.getAllByLabelText(/Explanation language/)[1] as HTMLSelectElement;
    await user.selectOptions(select, "en");
    await waitFor(() => expect(screen.getByTestId("guidance-body")).toHaveAttribute("data-language", "en"));

    // Description changed language...
    expect(screen.getByText(GUIDANCE_TEXT.en)).toBeInTheDocument();
    expect(screen.queryByText(GUIDANCE_TEXT.ur)).not.toBeInTheDocument();
    // ...while the answer and the printed label did not.
    expect((screen.getByLabelText("Your answer") as HTMLInputElement).value).toBe("Mahesh Rao");
    expect(screen.getByRole("heading", { name: urduField.label })).toHaveAttribute("dir", "rtl");

    await user.selectOptions(select, "kn");
    await waitFor(() => expect(screen.getByText(GUIDANCE_TEXT.kn)).toBeInTheDocument());
    expect((screen.getByLabelText("Your answer") as HTMLInputElement).value).toBe("Mahesh Rao");

    await user.selectOptions(select, "hi");
    await waitFor(() => expect(screen.getByText(GUIDANCE_TEXT.hi)).toBeInTheDocument());
    expect((screen.getByLabelText("Your answer") as HTMLInputElement).value).toBe("Mahesh Rao");
  });

  it("remembers the chosen language instead of re-applying the form's script", async () => {
    const user = userEvent.setup();
    render(<App />);
    await uploadAndWait(user);
    const select = screen.getAllByLabelText(/Explanation language/)[1] as HTMLSelectElement;
    await user.selectOptions(select, "kn");
    await waitFor(() => expect(localStorage.getItem("formsathi.language")).toBe("kn"));
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
    rerender(
      <FieldNavigator
        fields={[field]}
        selectedId={null}
        excluded={new Set()}
        onSelect={onSelect}
        onExclude={vi.fn()}
      />,
    );
    await user.click(screen.getByText("Full Name"));
    expect(onSelect).toHaveBeenCalledTimes(2);
  });

  it("shows source badge and low-confidence warning", () => {
    render(<SourceBadge source="known_form_knowledge_base" />);
    expect(screen.getByTestId("source-badge")).toHaveTextContent("Known Form Knowledge Base");
    render(
      <FieldNavigator fields={[field]} selectedId={null} excluded={new Set()} onSelect={vi.fn()} onExclude={vi.fn()} />,
    );
    expect(screen.getByText("Low confidence")).toBeInTheDocument();
  });

  it("names a page-read source distinctly from a dictionary match", () => {
    render(<SourceBadge source="page_interpretation" />);
    expect(screen.getByTestId("source-badge")).toHaveTextContent("Read From This Page");
  });

  it("shows the disambiguated name, not the repeated printed caption", () => {
    // Two cells captioned "Name:" under different column headers are different
    // questions. Showing both as "Name" is the bug this guards against.
    const elector: DetectedField = { ...field, id: "a", label: "Name:", display_label: "Elector's name (last SIR)" };
    const relative: DetectedField = { ...field, id: "b", label: "Name:", display_label: "Relative's name (last SIR)" };
    render(
      <FieldNavigator
        fields={[elector, relative]}
        selectedId={null}
        excluded={new Set()}
        onSelect={vi.fn()}
        onExclude={vi.fn()}
      />,
    );
    expect(screen.getByText("Elector's name (last SIR)")).toBeInTheDocument();
    expect(screen.getByText("Relative's name (last SIR)")).toBeInTheDocument();
    expect(screen.queryByText("Name:")).not.toBeInTheDocument();
  });

  it("marks a field the office fills in", () => {
    const blo: DetectedField = { ...field, id: "c", label: "BLO's Signature", filled_by: "office", confidence: 0.9 };
    render(
      <FieldNavigator fields={[blo]} selectedId={null} excluded={new Set()} onSelect={vi.fn()} onExclude={vi.fn()} />,
    );
    expect(screen.getByTestId("office-badge")).toHaveTextContent("Office use");
  });

  it("refuses to offer an answer box for an office field", () => {
    const blo: DetectedField = { ...field, id: "d", label: "BLO's Signature", filled_by: "office", confidence: 0.9 };
    render(<FieldInput field={blo} value="" onChange={vi.fn()} />);
    expect(screen.getByText(/filled in by the office/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Your answer")).not.toBeInTheDocument();
  });

  it("names the inferred source distinctly from a dictionary match", () => {
    render(<SourceBadge source="label_pattern_heuristic" />);
    expect(screen.getByTestId("source-badge")).toHaveTextContent("Inferred From Printed Label");
  });

  it("renders text in the direction of its own language", () => {
    const { container } = render(
      <>
        <DirectionalText language="ur">اردو</DirectionalText>
        <DirectionalText language="hi">हिन्दी</DirectionalText>
      </>,
    );
    const paragraphs = container.querySelectorAll("p");
    expect(paragraphs[0]).toHaveAttribute("dir", "rtl");
    expect(paragraphs[0]).toHaveAttribute("lang", "ur-IN");
    expect(paragraphs[1]).toHaveAttribute("dir", "ltr");
  });

  it("shows voice fallback", () => {
    render(<VoiceButton onPlay={vi.fn()} onStop={vi.fn()} speaking={false} available={false} hasLanguageVoice={false} />);
    expect(screen.getByText(/Voice is not available/)).toBeInTheDocument();
  });

  it("disables play when no voice can read the language, and names it", () => {
    // The engine returns silence rather than an error when nothing can read the
    // language, so a button left enabled would simply never do anything.
    const onPlay = vi.fn();
    render(
      <VoiceButton
        onPlay={onPlay}
        onStop={vi.fn()}
        speaking={false}
        available
        hasLanguageVoice={false}
        canSpeak={false}
        language="kn"
      />,
    );
    const play = screen.getByLabelText("Play guidance");
    expect(play).toBeDisabled();
    expect(screen.getByTestId("no-voice-notice")).toHaveTextContent("ಕನ್ನಡ");
  });

  it("enables play when a voice is installed", () => {
    render(
      <VoiceButton onPlay={vi.fn()} onStop={vi.fn()} speaking={false} available hasLanguageVoice language="en" />,
    );
    expect(screen.getByLabelText("Play guidance")).toBeEnabled();
    expect(screen.queryByTestId("no-voice-notice")).not.toBeInTheDocument();
  });
});

describe("answer validation", () => {
  const withRule = (kind: string, extra: Record<string, unknown> = {}) => ({
    ...field,
    confidence: 0.9,
    validation_rule: {
      kind,
      pattern: null,
      message: null,
      format: null,
      optional: false,
      min_value: null,
      max_value: null,
      max_length: null,
      ...extra,
    },
  });

  it("validates dates", () => {
    expect(validateAnswer({ ...field, field_type: "date", confidence: 0.9 }, "99")).toMatch(/date/i);
    expect(validateAnswer({ ...field, field_type: "date", confidence: 0.9 }, "99/99/1998")).toMatch(/real calendar/);
    expect(validateAnswer({ ...field, field_type: "date", confidence: 0.9 }, "15/08/1998")).toBeNull();
  });

  it("applies the rule attached to an unknown-form field", () => {
    expect(validateAnswer(withRule("mobile_in"), "9876500000")).toBeNull();
    expect(validateAnswer(withRule("mobile_in"), "12345")).toMatch(/ten digits/);
    expect(validateAnswer(withRule("pincode_in"), "560001")).toBeNull();
    expect(validateAnswer(withRule("pincode_in"), "056000")).toMatch(/six digits/);
    expect(validateAnswer(withRule("aadhaar_in"), "999988887777")).toBeNull();
    expect(validateAnswer(withRule("aadhaar_in"), "123")).toMatch(/twelve digits/);
    expect(validateAnswer(withRule("pan_in"), "ABCDE1234F")).toBeNull();
    expect(validateAnswer(withRule("pan_in"), "ABC123")).toMatch(/ABCDE1234F/);
    expect(validateAnswer(withRule("ifsc_in"), "DEMO0001234")).toBeNull();
    expect(validateAnswer(withRule("email"), "a@b.com")).toBeNull();
    expect(validateAnswer(withRule("email"), "nope")).toMatch(/name@example.com/);
    expect(validateAnswer(withRule("person_name"), "Ananya Rao")).toBeNull();
    expect(validateAnswer(withRule("person_name"), "Ananya 42")).toMatch(/digits/);
  });

  it("accepts digits typed on a Hindi, Kannada, or Urdu keyboard", () => {
    expect(foldDigits("९८७६५००००० ")).toBe("9876500000 ");
    expect(foldDigits("೫೬೦೦೦೧")).toBe("560001");
    expect(foldDigits("۵۶۰۰۰۱")).toBe("560001");
    expect(validateAnswer(withRule("mobile_in"), "९८७६५०००००")).toBeNull();
    expect(validateAnswer(withRule("pincode_in"), "೫೬೦೦೦೧")).toBeNull();
    expect(validateAnswer(withRule("pincode_in"), "۵۶۰۰۰۱")).toBeNull();
  });

  it("warns when a value is too long for the printed space", () => {
    expect(validateAnswer(withRule("text", { max_length: 5 }), "far too long")).toMatch(/longer than 5/);
    expect(validateAnswer(withRule("text", { max_length: 20 }), "fits")).toBeNull();
  });

  it("leaves an empty optional field alone", () => {
    expect(validateAnswer(withRule("mobile_in", { optional: true }), "")).toBeNull();
    expect(validateAnswer(withRule("aadhaar_in"), "  ")).toBeNull();
  });
});

describe("preview and reset", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("requests a preview in the current explanation language and can start a new form", async () => {
    const user = userEvent.setup();
    const { createPreview } = await import("../api/client");
    render(<App />);
    await uploadAndWait(user);
    await user.click(await screen.findByText("Create completed reference preview"));
    expect(await screen.findByText("Completed Reference Preview")).toBeInTheDocument();
    expect(screen.getByText("Download PDF")).toBeInTheDocument();
    expect(vi.mocked(createPreview).mock.calls[0][2]).toBe("ur");
    await user.click(screen.getByText("Start new form"));
    expect(await screen.findByText(/Drop a PNG/)).toBeInTheDocument();
  });

  it("retries a cold backend before giving up, then says how to start it", async () => {
    const { fetchConfig, ApiError } = await import("../api/client");
    vi.mocked(fetchConfig).mockReset();
    vi.mocked(fetchConfig).mockRejectedValue(new ApiError("Something went wrong. Please try again.", "down", 503));
    render(<App />);

    // The backend binds its port only after loading an embedding model, so the first
    // call failing is expected and must not be reported as a fault straight away.
    await waitFor(() => expect(fetchConfig).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    // The retries are real two-second waits, so the margins here are generous on
    // purpose: a tighter bound makes this test fail on a loaded machine rather than on
    // a real regression.
    await waitFor(() => expect(fetchConfig).toHaveBeenCalledTimes(6), { timeout: 30000 });
    const alerts = await screen.findAllByRole("alert", {}, { timeout: 15000 });
    expect(alerts[0]).toHaveTextContent("port 8000");
    expect(alerts[0]).toHaveTextContent("uvicorn");
  }, 60000);

  it("recovers without an error when the backend comes up on a retry", async () => {
    const { fetchConfig, ApiError } = await import("../api/client");
    vi.mocked(fetchConfig).mockReset();
    vi.mocked(fetchConfig)
      .mockRejectedValueOnce(new ApiError("Something went wrong. Please try again.", "down", 503))
      .mockResolvedValue({
        llm_configured: false,
        external_ai_enabled: false,
        max_upload_mb: 10,
        max_pdf_pages: 5,
        languages: ["en", "hi", "kn", "ur"],
        language_details: [],
        categories: ["banking"],
        accepted_types: ["image/png"],
        dictionary_fields: 56,
        label_patterns: 7,
        ocr_languages: "eng+hin+kan+urd",
        privacy_notice: "Academic demonstration privacy notice.",
      } as never);
    render(<App />);
    expect(await screen.findByText(/Drop a PNG/, {}, { timeout: 20000 })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  }, 40000);
});
