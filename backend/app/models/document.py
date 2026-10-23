from datetime import datetime

from pydantic import BaseModel, Field

from app.models.common import (
    DocumentCategory,
    DocumentStatus,
    Language,
    ProcessingStage,
)
from app.models.fields import DetectedField
from app.models.interpretation import ClassifiedField, FormContext, InterpretedField
from app.models.ocr import OCRResult


class DocumentPage(BaseModel):
    index: int
    original_path: str
    processed_path: str | None = None
    width: int
    height: int
    detection_succeeded: bool = False


class KnownFormMatch(BaseModel):
    form_id: str | None = None
    display_name: str | None = None
    category: DocumentCategory | None = None
    score: float = 0.0
    matched_terms: list[str] = Field(default_factory=list)
    unknown: bool = True


class DocumentRecord(BaseModel):
    id: str
    original_filename: str
    original_path: str = ""
    mime_type: str
    category: DocumentCategory = DocumentCategory.OTHER
    status: DocumentStatus = DocumentStatus.PROCESSING
    stage: ProcessingStage = ProcessingStage.VALIDATING
    pages: list[DocumentPage] = Field(default_factory=list)
    ocr: list[OCRResult] = Field(default_factory=list)
    fields: list[DetectedField] = Field(default_factory=list)
    form_match: KnownFormMatch = Field(default_factory=KnownFormMatch)
    # Scripts actually found on the page, and the explanation language to open with.
    # Neither alters the uploaded form; both only pick sensible interface defaults.
    scripts: list[str] = Field(default_factory=list)
    suggested_language: Language = Language.ENGLISH
    # What the interpreter made of each blank. `classified` is the compact English
    # reading of every blank; `interpreted` holds the four-language text for the blanks
    # the authored dictionary could not serve. Both are keyed by field id.
    classified: dict[str, ClassifiedField] = Field(default_factory=dict)
    interpreted: dict[str, InterpretedField] = Field(default_factory=dict)
    interpreter_used: bool = False
    # What the document turned out to be, read once before any field was described.
    form_context: FormContext | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentResponse(BaseModel):
    id: str
    original_filename: str
    status: DocumentStatus
    stage: ProcessingStage
    category: DocumentCategory
    page_count: int
    fields: list[DetectedField] = Field(default_factory=list)
    form_match: KnownFormMatch
    scripts: list[str] = Field(default_factory=list)
    suggested_language: Language = Language.ENGLISH
    interpreter_used: bool = False
    form_context: FormContext | None = None
    error_message: str | None = None
    llm_configured: bool = False
    created_at: datetime
