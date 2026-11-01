import type { DetectedField } from "../types";

export function isApplicantBlank(field: DetectedField): boolean {
  if (field.field_type === "signature") {
    return false;
  }
  if (field.filled_by === "office") {
    return false;
  }
  const rule = field.validation_rule;
  if (rule?.optional || rule?.kind === "office_use") {
    return false;
  }
  return true;
}

export function isRequiredField(field: DetectedField): boolean {
  return Boolean(field.required) && isApplicantBlank(field);
}

export function isAnswered(field: DetectedField, answers: Record<string, string>): boolean {
  return Boolean((answers[field.id] ?? "").trim());
}

export function missingRequiredFields(
  fields: DetectedField[],
  answers: Record<string, string>,
  excluded: Set<string> = new Set(),
): DetectedField[] {
  return fields.filter(
    (field) => isRequiredField(field) && !excluded.has(field.id) && !isAnswered(field, answers),
  );
}

export const REQUIRED_LEGEND = "* Indicates required question";
export const REQUIRED_ERROR = "This is a required question";
export const REQUIRED_BLOCKED = "Fill every required question marked with * before creating the preview.";
