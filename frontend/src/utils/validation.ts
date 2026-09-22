import type { CSSProperties } from "react";
import type { DetectedField } from "../types";

const ACCEPT = ["image/png", "image/jpeg", "image/jpg", "image/webp", "application/pdf"];

export function validateUpload(file: File, maxMb = 10): string | null {
  if (!ACCEPT.includes(file.type) && !/\.(png|jpe?g|webp|pdf)$/i.test(file.name)) {
    return "Please upload a PNG, JPG, JPEG, WEBP, or PDF form.";
  }
  if (file.size > maxMb * 1024 * 1024) {
    return `Please choose a file smaller than ${maxMb} MB.`;
  }
  return null;
}

export function validateAnswer(field: DetectedField, value: string): string | null {
  if (field.field_type === "date" && value && !/^\d{2}\/\d{2}\/\d{4}$/.test(value) && !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return "Use a date such as DD/MM/YYYY.";
  }
  return null;
}

export function overlayStyle(box: { x: number; y: number; width: number; height: number }): CSSProperties {
  return {
    left: `${box.x * 100}%`,
    top: `${box.y * 100}%`,
    width: `${box.width * 100}%`,
    height: `${box.height * 100}%`,
  };
}
