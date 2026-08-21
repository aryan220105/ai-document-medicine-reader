from __future__ import annotations

import re

from app.models.document import DetectedField
from app.models.ocr import OCRResult, OCRWord
from app.utils.boxes import boxes_from_words
from app.utils.text import fold, normalize_text


MONTH_PATTERN = (
    r"(?:JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|"
    r"JUL(?:Y)?|AUG(?:UST)?|SEP(?:T(?:EMBER)?)?|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)"
)
DATE_TOKEN = (
    rf"(?:(?:{MONTH_PATTERN})\s+\d{{4}}|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|"
    rf"\d{{1,2}}\s+{MONTH_PATTERN}\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})"
)
AMOUNT_RE = re.compile(
    r"(?:(?:rs\.?|inr|₹)\s*)([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
STRENGTH_RE = re.compile(r"\b(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu))\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b")
ACCOUNT_RE = re.compile(
    r"(?:account|a/c|consumer|acct)(?:\s*(?:no\.?|number|#))?[:\s-]+([A-Z0-9-]*\d[A-Z0-9-]{3,17})",
    re.IGNORECASE,
)
REFERENCE_RE = re.compile(
    r"(?:reference|invoice|policy)(?:\s*(?:no\.?|number|#))?[:\s-]+([A-Z0-9/-]*\d[A-Z0-9/-]{2,19})",
    re.IGNORECASE,
)
BATCH_RE = re.compile(r"(?:batch|b\.?\s*no\.?|lot)[:\s-]*([A-Z0-9-]{3,16})", re.IGNORECASE)
EXPIRY_RE = re.compile(
    rf"(?:exp(?:iry)?|use before|best before|use by)[:\s-]*({DATE_TOKEN})",
    re.IGNORECASE,
)
MFG_RE = re.compile(
    rf"(?:mfg|mfd|manufactur(?:ed|ing)\s*date)[:\s-]*({DATE_TOKEN})",
    re.IGNORECASE,
)
DUE_RE = re.compile(
    rf"(?:due date|pay by|payment due|last date)[:\s-]*({DATE_TOKEN})",
    re.IGNORECASE,
)
GENERIC_DATE_RE = re.compile(DATE_TOKEN, re.IGNORECASE)


class ExtractionService:
    def extract(self, ocr: OCRResult) -> list[DetectedField]:
        text = ocr.full_text
        fields: list[DetectedField] = []
        fields.extend(self._named_date_fields(ocr, text))
        fields.extend(self._regex_fields(ocr, text, STRENGTH_RE, "strength", "Strength"))
        fields.extend(self._regex_fields(ocr, text, BATCH_RE, "batch_number", "Batch"))
        fields.extend(self._amount_fields(ocr, text))
        fields.extend(self._regex_fields(ocr, text, ACCOUNT_RE, "account_number", "Account Number"))
        fields.extend(self._regex_fields(ocr, text, REFERENCE_RE, "reference_number", "Reference Number"))
        fields.extend(self._regex_fields(ocr, text, EMAIL_RE, "email", "Email"))
        fields.extend(self._regex_fields(ocr, text, PHONE_RE, "phone", "Phone"))
        medicine = self._medicine_name(ocr)
        if medicine:
            fields.append(medicine)
        dosage = self._dosage(ocr)
        if dosage:
            fields.append(dosage)
        warnings = self._warnings(ocr)
        if warnings:
            fields.append(warnings)
        storage = self._storage(ocr)
        if storage:
            fields.append(storage)
        return self._dedupe(fields)

    def _named_date_fields(self, ocr: OCRResult, text: str) -> list[DetectedField]:
        fields: list[DetectedField] = []
        for pattern, field_type, label in (
            (EXPIRY_RE, "expiry_date", "Expiry"),
            (MFG_RE, "manufacturing_date", "Manufacturing Date"),
            (DUE_RE, "due_date", "Due Date"),
        ):
            match = pattern.search(text)
            if match:
                value = normalize_text(match.group(1))
                fields.append(self._field_from_value(ocr, field_type, value, label, extra=0.12))
        if not any(field.field_type == "due_date" for field in fields):
            for match in GENERIC_DATE_RE.finditer(text):
                window = text[max(0, match.start() - 24): match.start()].lower()
                if "due" in window or "pay" in window:
                    value = normalize_text(match.group(0))
                    fields.append(self._field_from_value(ocr, "due_date", value, "Due Date", extra=0.05))
                    break
        return fields

    def _amount_fields(self, ocr: OCRResult, text: str) -> list[DetectedField]:
        fields: list[DetectedField] = []
        for match in AMOUNT_RE.finditer(text):
            raw = match.group(1)
            if not raw:
                continue
            window = text[max(0, match.start() - 30): match.end() + 8].lower()
            if any(token in window for token in ("amount", "payable", "total", "due", "bill", "premium", "rs", "inr", "₹")):
                value = f"₹{raw}" if "₹" in match.group(0) or "rs" in window or "inr" in window else raw
                fields.append(self._field_from_value(ocr, "amount", value, "Amount", extra=0.1))
                break
        return fields

    def _regex_fields(
        self,
        ocr: OCRResult,
        text: str,
        pattern: re.Pattern[str],
        field_type: str,
        label: str,
    ) -> list[DetectedField]:
        match = pattern.search(text)
        if not match:
            return []
        value = normalize_text(match.group(1) if match.lastindex else match.group(0))
        return [self._field_from_value(ocr, field_type, value, label)]

    def _medicine_name(self, ocr: OCRResult) -> DetectedField | None:
        skip = {"tablets", "tablet", "capsules", "capsule", "syrup", "batch", "mfg", "exp", "dosage", "store"}
        for line in ocr.lines[:6]:
            folded = fold(line)
            if any(marker in folded for marker in ("batch", "mfg", "exp", "dosage", "store", "account", "bill")):
                continue
            tokens = [token for token in line.split() if fold(token) not in skip]
            if tokens and any(token.isalpha() and len(token) > 3 for token in tokens):
                value = normalize_text(" ".join(tokens[:6]))
                return self._field_from_value(ocr, "medicine_name", value, "Medicine / Product", extra=0.05)
        return None

    def _dosage(self, ocr: OCRResult) -> DetectedField | None:
        for line in ocr.lines:
            folded = fold(line)
            if "dosage" in folded or "directed by" in folded or "take one" in folded or "twice daily" in folded:
                value = normalize_text(re.sub(r"^dosage[:\s-]*", "", line, flags=re.IGNORECASE))
                return self._field_from_value(ocr, "dosage", value, "Dosage")
        return None

    def _warnings(self, ocr: OCRResult) -> DetectedField | None:
        for line in ocr.lines:
            folded = fold(line)
            if any(token in folded for token in ("warning", "caution", "keep out of reach", "not for")):
                return self._field_from_value(ocr, "warnings", normalize_text(line), "Warnings")
        return None

    def _storage(self, ocr: OCRResult) -> DetectedField | None:
        for line in ocr.lines:
            folded = fold(line)
            if "store" in folded or "storage" in folded:
                return self._field_from_value(ocr, "storage", normalize_text(line), "Storage")
        return None

    def _field_from_value(
        self,
        ocr: OCRResult,
        field_type: str,
        value: str,
        label: str,
        extra: float = 0.0,
    ) -> DetectedField:
        words = self._locate_words(ocr.words, value)
        if not words:
            words = self._locate_words(ocr.words, value.split()[-1] if value.split() else value)
        boxes = boxes_from_words(words, label=label)
        ocr_conf = sum(word.confidence for word in words) / len(words) if words else ocr.average_confidence
        confidence = min(1.0, (ocr_conf / 100.0) * 0.85 + extra)
        uncertain = confidence < 0.65 or ocr_conf < 65
        return DetectedField(
            field_type=field_type,
            value=value,
            confidence=round(confidence, 3),
            word_ids=[word.id for word in words],
            bounding_boxes=boxes,
            uncertain=uncertain,
            label=label,
        )

    def _locate_words(self, words: list[OCRWord], phrase: str) -> list[OCRWord]:
        needles = [fold(token) for token in re.findall(r"[A-Za-z0-9₹./:-]+", phrase) if token]
        if not needles:
            return []
        folded_words = [fold(word.text) for word in words]
        for start in range(len(words)):
            if folded_words[start] != needles[0] and needles[0] not in folded_words[start]:
                continue
            matched = [words[start]]
            needle_index = 1
            cursor = start + 1
            while needle_index < len(needles) and cursor < len(words):
                if needles[needle_index] in folded_words[cursor] or folded_words[cursor] in needles[needle_index]:
                    matched.append(words[cursor])
                    needle_index += 1
                elif abs(words[cursor].line_id - words[start].line_id) > 1:
                    break
                cursor += 1
            if needle_index == len(needles):
                return matched
        return [word for word in words if any(needle in fold(word.text) for needle in needles[:2])]

    def _dedupe(self, fields: list[DetectedField]) -> list[DetectedField]:
        best: dict[str, DetectedField] = {}
        for field in fields:
            current = best.get(field.field_type)
            if current is None or field.confidence > current.confidence:
                best[field.field_type] = field
        return list(best.values())
