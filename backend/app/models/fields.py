from pydantic import BaseModel, Field

from app.models.common import FieldType, NormalizedBoundingBox


class FieldOption(BaseModel):
    id: str
    label: str
    box: NormalizedBoundingBox


class DetectedField(BaseModel):
    id: str
    page_index: int
    label: str
    field_type: FieldType
    input_box: NormalizedBoundingBox
    label_boxes: list[NormalizedBoundingBox] = Field(default_factory=list)
    source_word_ids: list[str] = Field(default_factory=list)
    options: list[FieldOption] = Field(default_factory=list)
    required: bool | None = None
    confidence: float
    confidence_reasons: list[str] = Field(default_factory=list)
    known_field_id: str | None = None


class ValidationRule(BaseModel):
    kind: str
    pattern: str | None = None
    message: str | None = None


class ValidationResult(BaseModel):
    ok: bool
    message: str | None = None


class FieldAnswer(BaseModel):
    field_id: str
    value: str = ""
    selected_option_ids: list[str] = Field(default_factory=list)
