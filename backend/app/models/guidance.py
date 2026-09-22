from pydantic import BaseModel, Field

from app.models.common import DocumentCategory, GuidanceSource, Language, NormalizedBoundingBox
from app.models.fields import ValidationRule


class FieldGuidance(BaseModel):
    field_id: str
    language: Language
    simple_label: str
    what_to_enter: str
    why_needed: str | None = None
    example: str | None = None
    format_hint: str | None = None
    validation_rule: ValidationRule | None = None
    source: GuidanceSource
    source_reference: str | None = None
    confidence: float
    requires_verification: bool = False
    highlights: list[NormalizedBoundingBox] = Field(default_factory=list)


class GuidanceRequest(BaseModel):
    field_id: str
    language: Language = Language.ENGLISH
    allow_external_ai: bool = False
    category: DocumentCategory | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    field_id: str | None = None
    language: Language = Language.ENGLISH
    allow_external_ai: bool = False


class AskResponse(BaseModel):
    answer: str
    source: GuidanceSource
    highlights: list[NormalizedBoundingBox] = Field(default_factory=list)
    llm_used: bool = False
    refused: bool = False


class LLMGuidancePayload(BaseModel):
    simple_label: str
    what_to_enter: str
    why_needed: str | None = None
    example: str | None = None
    format_hint: str | None = None
    requires_verification: bool = True
