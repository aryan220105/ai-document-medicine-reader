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

    @property
    def has_useful_text(self) -> bool:
        return len(" ".join(self.full_text.split())) >= 8 and len(self.words) >= 2
