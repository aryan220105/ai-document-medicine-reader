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

/**
 * Immediate, client-side feedback while typing. The backend holds the authoritative
 * rules; this is a fast first pass so the user is not left waiting on a request.
 * Indic and Arabic digit forms are folded so a value typed on a Hindi, Kannada, or Urdu
 * keyboard is judged the same way Latin digits are.
 */
const DIGIT_FOLD: Record<string, string> = {};
for (let i = 0; i < 10; i += 1) {
  DIGIT_FOLD[String.fromCharCode(0x0966 + i)] = String(i); // Devanagari
  DIGIT_FOLD[String.fromCharCode(0x0ce6 + i)] = String(i); // Kannada
  DIGIT_FOLD[String.fromCharCode(0x0660 + i)] = String(i); // Arabic-Indic
  DIGIT_FOLD[String.fromCharCode(0x06f0 + i)] = String(i); // Urdu
}

export function foldDigits(value: string): string {
  return value.replace(/./gu, (char) => DIGIT_FOLD[char] ?? char);
}

function digitsOnly(value: string): string {
  return foldDigits(value).replace(/\D/g, "");
}

const CHECKS: Record<string, (value: string) => string | null> = {
  date: (value) => {
    const folded = foldDigits(value).trim();
    const dayFirst = folded.match(/^(\d{2})[/\-.](\d{2})[/\-.](\d{4})$/);
    const yearFirst = folded.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    const match = dayFirst ?? yearFirst;
    if (!match) {
      return "Use a date such as DD/MM/YYYY.";
    }
    const year = Number(yearFirst ? match[1] : match[3]);
    const month = Number(match[2]);
    const day = Number(yearFirst ? match[3] : match[1]);
    const date = new Date(year, month - 1, day);
    if (
      month < 1 ||
      month > 12 ||
      day < 1 ||
      date.getFullYear() !== year ||
      date.getMonth() !== month - 1 ||
      date.getDate() !== day
    ) {
      return "That is not a real calendar date.";
    }
    return null;
  },
  year: (value) => (/^\d{4}$/.test(value) ? null : "Write a four-digit year, such as 2024."),
  mobile_in: (value) => {
    let digits = digitsOnly(value);
    if (digits.length === 12 && digits.startsWith("91")) {
      digits = digits.slice(2);
    }
    return digits.length === 10 && /^[6-9]/.test(digits)
      ? null
      : "An Indian mobile number has ten digits and starts with 6, 7, 8, or 9.";
  },
  pincode_in: (value) => {
    const digits = digitsOnly(value);
    return digits.length === 6 && !digits.startsWith("0") ? null : "An Indian PIN code has six digits and does not start with 0.";
  },
  aadhaar_in: (value) => {
    const digits = digitsOnly(value);
    return digits.length === 12 && !/^[01]/.test(digits) ? null : "An Aadhaar number has twelve digits. Copy it from the card.";
  },
  pan_in: (value) =>
    /^[A-Z]{5}[0-9]{4}[A-Z]$/.test(value.replace(/\s/g, "").toUpperCase())
      ? null
      : "A PAN looks like ABCDE1234F.",
  ifsc_in: (value) =>
    /^[A-Z]{4}0[A-Z0-9]{6}$/.test(value.replace(/\s/g, "").toUpperCase())
      ? null
      : "An IFSC looks like DEMO0001234.",
  bank_account: (value) => {
    const digits = digitsOnly(value);
    return digits.length >= 8 && digits.length <= 20 ? null : "Bank account numbers are usually 8 to 20 digits.";
  },
  email: (value) => (/^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$/.test(value) ? null : "An email address looks like name@example.com."),
  blood_group: (value) => (/^(A|B|AB|O)[+-]$/i.test(value.replace(/\s/g, "")) ? null : "Write a blood group such as A+, B-, O+, or AB+."),
  integer: (value) => (/^\d+$/.test(foldDigits(value)) ? null : "Use digits only for this field."),
  amount: (value) =>
    /^\d+(\.\d{1,2})?$/.test(foldDigits(value).replace(/[,\s₹]/g, "").replace(/^Rs\.?/i, ""))
      ? null
      : "Write the amount in figures, such as 5000.",
  decimal: (value) => (/^\d+(\.\d+)?$/.test(foldDigits(value)) ? null : "Write a number in this field."),
  person_name: (value) => (/\d/.test(foldDigits(value)) ? "A name should not contain digits. Check this value." : null),
};

export function validateAnswer(field: DetectedField, value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const rule = field.validation_rule ?? null;
  if (rule?.max_length && trimmed.length > rule.max_length) {
    return `This value is longer than ${rule.max_length} characters and may not fit the printed space.`;
  }
  const kind = rule?.kind ?? (field.field_type === "date" ? "date" : "text");
  const check = CHECKS[kind];
  if (check) {
    const message = check(trimmed);
    if (message) {
      return rule?.message ?? message;
    }
  }
  if (field.field_type === "date" && !rule) {
    return CHECKS.date(trimmed);
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
