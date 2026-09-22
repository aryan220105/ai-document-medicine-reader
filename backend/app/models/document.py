from datetime import datetime

from pydantic import BaseModel, Field

from app.models.common import (
    DocumentCategory,
    DocumentStatus,
    ProcessingStage,
)
from app.models.fields import DetectedField
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
    error_message: str | None = None
    llm_configured: bool = False
    created_at: datetime
