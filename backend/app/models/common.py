from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    KANNADA = "kn"


class DocumentType(str, Enum):
    MEDICINE_LABEL = "medicine_label"
    ELECTRICITY_BILL = "electricity_bill"
    BANK_DOCUMENT = "bank_document"
    INSURANCE_DOCUMENT = "insurance_document"
    GOVERNMENT_NOTICE = "government_notice"
    TAX_DOCUMENT = "tax_document"
    GENERAL_DOCUMENT = "general_document"
    UNKNOWN = "unknown"


class ProcessingStage(str, Enum):
    UPLOADING = "uploading"
    DETECTING = "detecting"
    ENHANCING = "enhancing"
    OCR = "ocr"
    EXTRACTING = "extracting"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class BoundingBox(BaseModel):
    x: float = Field(ge=0, le=1.5)
    y: float = Field(ge=0, le=1.5)
    width: float = Field(ge=0, le=1.5)
    height: float = Field(ge=0, le=1.5)
    label: str | None = None


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def confidence_level(score: float) -> ConfidenceLevel:
    if score >= 85:
        return ConfidenceLevel.HIGH
    if score >= 65:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW
