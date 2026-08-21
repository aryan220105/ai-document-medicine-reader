from datetime import datetime

from pydantic import BaseModel, Field

from app.models.common import (
    BoundingBox,
    DocumentStatus,
    DocumentType,
    ProcessingStage,
)
from app.models.ocr import OCRResult


class DetectedField(BaseModel):
    field_type: str
    value: str
    confidence: float
    word_ids: list[int] = Field(default_factory=list)
    bounding_boxes: list[BoundingBox] = Field(default_factory=list)
    uncertain: bool = False
    label: str | None = None


class KnowledgeChunk(BaseModel):
    chunk_id: str
    text: str
    source: str
    title: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    chunk_id: str
    text: str
    source: str
    score: float
    word_ids: list[int] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class DocumentRecord(BaseModel):
    id: str
    original_filename: str
    original_path: str
    processed_path: str | None = None
    mime_type: str
    status: DocumentStatus = DocumentStatus.PROCESSING
    stage: ProcessingStage = ProcessingStage.UPLOADING
    document_type: DocumentType = DocumentType.UNKNOWN
    user_document_type: DocumentType | None = None
    detection_succeeded: bool = False
    ocr: OCRResult | None = None
    fields: list[DetectedField] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def effective_type(self) -> DocumentType:
        return self.user_document_type or self.document_type


class DocumentSummary(BaseModel):
    id: str
    original_filename: str
    status: DocumentStatus
    stage: ProcessingStage
    document_type: DocumentType
    detection_succeeded: bool = False
    average_confidence: float = 0.0
    error_message: str | None = None
    created_at: datetime


class DocumentResponse(BaseModel):
    id: str
    original_filename: str
    status: DocumentStatus
    stage: ProcessingStage
    document_type: DocumentType
    detection_succeeded: bool
    average_confidence: float = 0.0
    confidence_level: str = "low"
    ocr_text: str = ""
    fields: list[DetectedField] = Field(default_factory=list)
    error_message: str | None = None
    original_image_url: str
    processed_image_url: str | None = None
    llm_configured: bool = False
    created_at: datetime


class DocumentTypeUpdate(BaseModel):
    document_type: DocumentType
