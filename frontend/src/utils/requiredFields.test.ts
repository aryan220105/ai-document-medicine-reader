import { describe, expect, it } from "vitest";
import type { DetectedField } from "../types";
import { isRequiredField, missingRequiredFields } from "./requiredFields";

const base: DetectedField = {
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
  filled_by: "applicant",
};

describe("required fields", () => {
  it("treats applicant blanks marked required as required", () => {
    expect(isRequiredField(base)).toBe(true);
    expect(isRequiredField({ ...base, required: false })).toBe(false);
    expect(isRequiredField({ ...base, filled_by: "office" })).toBe(false);
    expect(isRequiredField({ ...base, field_type: "signature" })).toBe(false);
  });

  it("lists only unanswered required blanks", () => {
    const dob: DetectedField = { ...base, id: "dob", label: "Date of Birth" };
    const missing = missingRequiredFields([base, dob], { "p0-f0": "Ravi" });
    expect(missing.map((field) => field.id)).toEqual(["dob"]);
  });
});
