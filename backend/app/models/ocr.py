from pydantic import BaseModel, Field

from app.models.common import NormalizedBoundingBox, PixelBoundingBox
from app.utils.bounding_boxes import normalize_box


class OCRWord(BaseModel):
    id: str
    text: str
    confidence: float
    page_index: int
    pixel: PixelBoundingBox
    line_id: int = 0
    block_id: int = 0
    # Set when the source already lists words in reading order. PDF text layers do.
    # Their x positions are not a safe sort key for Urdu.
    reading_index: int | None = None

    @property
    def box(self) -> NormalizedBoundingBox:
        return normalize_box(self.pixel, label=self.text)


class OCRLine(BaseModel):
    id: int
    text: str
    word_ids: list[str] = Field(default_factory=list)
    box: NormalizedBoundingBox | None = None


class OCRResult(BaseModel):
    page_index: int = 0
    full_text: str = ""
    average_confidence: float = 0.0
    image_width: int = 0
    image_height: int = 0
    words: list[OCRWord] = Field(default_factory=list)
    lines: list[OCRLine] = Field(default_factory=list)

    # Which script the page turned out to be printed in, and which Tesseract models were
    # used to read it. Reported so the interface can offer a sensible default explanation
    # language; the form's own text is never translated.
    script: str = "unknown"
    languages_used: list[str] = Field(default_factory=list)
    rtl: bool = False

    @property
    def has_useful_text(self) -> bool:
        return len(" ".join(self.full_text.split())) >= 8 and len(self.words) >= 2
