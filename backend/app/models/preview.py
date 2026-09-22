from pydantic import BaseModel, Field

from app.models.fields import FieldAnswer


class PreviewRequest(BaseModel):
    answers: list[FieldAnswer] = Field(default_factory=list)
    language: str = "en"


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
