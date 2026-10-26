from pydantic import BaseModel, Field

from app.models.common import Language
from app.models.fields import FieldAnswer


class PreviewRequest(BaseModel):
    answers: list[FieldAnswer] = Field(default_factory=list)
    # Language for the warning messages only. The form's own content is never translated.
    language: Language = Language.ENGLISH


class PreviewWarning(BaseModel):
    field_id: str
    code: str
    message: str


class PreviewResult(BaseModel):
    preview_id: str
    pdf_url: str = ""
    pdf_path: str | None = None
    image_paths: list[str] = Field(default_factory=list)
    warnings: list[PreviewWarning] = Field(default_factory=list)
