from pydantic import BaseModel, Field

from app.models.common import FieldType, NormalizedBoundingBox


class FieldOption(BaseModel):
    id: str
    label: str
    box: NormalizedBoundingBox


class ValidationRule(BaseModel):
    kind: str
    pattern: str | None = None
    message: str | None = None
    format: str | None = None
    optional: bool = False
    min_value: float | None = None
    max_value: float | None = None
    max_length: int | None = None


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

    # Unknown-form resolution. `semantic_id` names the common-dictionary row the printed
    # label was resolved to, so answer entry, validation, and the preview behave the same
    # way they do on a known form.
    semantic_id: str | None = None
    semantic_score: float = 0.0
    semantic_source: str | None = None
    label_pattern_id: str | None = None
    validation_rule: ValidationRule | None = None
    label_script: str | None = None
    label_language: str | None = None

    # Where this blank sits on the page. A caption alone is often ambiguous -- a form can
    # print "Name:" twice on one row under different column headings -- so the headings
    # travel with the field and are what let it be explained and named correctly.
    caption: str = ""
    column_header: str = ""
    sub_header: str = ""
    section_hint: str = ""
    structure_origin: str = ""

    # Set once the page has been interpreted. `display_label` is the disambiguated name
    # shown in the interface, which is why two side-by-side "Name:" cells no longer read
    # identically in the field list.
    display_label: str = ""
    filled_by: str = "applicant"


class ValidationResult(BaseModel):
    ok: bool
    message: str | None = None


class FieldAnswer(BaseModel):
    field_id: str
    value: str = ""
    selected_option_ids: list[str] = Field(default_factory=list)
