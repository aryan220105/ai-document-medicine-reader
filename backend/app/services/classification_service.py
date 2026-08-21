from __future__ import annotations

from app.models.common import DocumentType
from app.models.ocr import OCRResult
from app.utils.text import fold


KEYWORD_MAP: list[tuple[DocumentType, tuple[str, ...]]] = [
    (
        DocumentType.MEDICINE_LABEL,
        ("tablet", "capsule", "syrup", "batch", "mfg", "exp", "dosage", "mg", "medicine", "store below"),
    ),
    (
        DocumentType.ELECTRICITY_BILL,
        ("electricity", "kwh", "units consumed", "consumer number", "sanctioned load", "energy charge"),
    ),
    (
        DocumentType.BANK_DOCUMENT,
        ("ifsc", "account statement", "savings account", "debit", "credit", "neft", "upi"),
    ),
    (
        DocumentType.INSURANCE_DOCUMENT,
        ("policy number", "premium", "sum insured", "claim", "insurer", "nominee"),
    ),
    (
        DocumentType.TAX_DOCUMENT,
        ("property tax", "assessment", "ward no", "holding number", "tax due"),
    ),
    (
        DocumentType.GOVERNMENT_NOTICE,
        ("government", "notice", "department", "circular", "ration", "municipality", "panchayat"),
    ),
]


class ClassificationService:
    def classify(self, ocr: OCRResult) -> DocumentType:
        text = fold(ocr.full_text)
        if not text:
            return DocumentType.UNKNOWN
        scores: dict[DocumentType, int] = {}
        for document_type, keywords in KEYWORD_MAP:
            scores[document_type] = sum(1 for keyword in keywords if keyword in text)
        best_type, best_score = max(scores.items(), key=lambda item: item[1])
        if best_score >= 2:
            return best_type
        if best_score == 1 and best_type in {DocumentType.MEDICINE_LABEL, DocumentType.ELECTRICITY_BILL}:
            return best_type
        if "bill" in text and "due" in text:
            return DocumentType.ELECTRICITY_BILL
        if "notice" in text:
            return DocumentType.GOVERNMENT_NOTICE
        return DocumentType.GENERAL_DOCUMENT
