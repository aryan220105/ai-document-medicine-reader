from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    KANNADA = "kn"


class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentCategory(str, Enum):
    GOVERNMENT = "government"
    BANKING = "banking"
    INSURANCE = "insurance"
    EDUCATION = "education"
    FINANCIAL = "financial"
    OTHER = "other"


class ProcessingStage(str, Enum):
    VALIDATING = "validating"
    PREPARING_PAGES = "preparing_pages"
    READING_TEXT = "reading_text"
    DETECTING_FIELDS = "detecting_fields"
    MATCHING_FORM = "matching_form"
    READY = "ready"
    FAILED = "failed"


class FieldType(str, Enum):
    TEXT = "text"
    MULTILINE = "multiline"
    DATE = "date"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SIGNATURE = "signature"
    TABLE_CELL = "table_cell"


class GuidanceSource(str, Enum):
    KNOWN_FORM = "known_form_knowledge_base"
    COMMON_DICTIONARY = "common_field_dictionary"
    FORM_TEXT = "printed_form_text"
    GENERAL_AI = "general_ai_guidance"
    UNAVAILABLE = "unavailable"


class PixelBoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int
    image_width: int
    image_height: int
    page_index: int = 0


class NormalizedBoundingBox(BaseModel):
    x: float = Field(ge=0, le=1.5)
    y: float = Field(ge=0, le=1.5)
    width: float = Field(ge=0, le=1.5)
    height: float = Field(ge=0, le=1.5)
    page_index: int = 0
    label: str | None = None

    def to_pixel(self, image_width: int, image_height: int) -> PixelBoundingBox:
        return PixelBoundingBox(
            x=int(self.x * image_width),
            y=int(self.y * image_height),
            width=max(1, int(self.width * image_width)),
            height=max(1, int(self.height * image_height)),
            image_width=image_width,
            image_height=image_height,
            page_index=self.page_index,
        )


class ApiError(BaseModel):
    code: str
    message: str
    details: dict[str, str] | None = None
