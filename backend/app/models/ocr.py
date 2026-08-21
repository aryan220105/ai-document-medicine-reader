from pydantic import BaseModel, Field

from app.models.common import BoundingBox, ConfidenceLevel, confidence_level


class OCRWord(BaseModel):
    id: int
    text: str
    confidence: float
    x: int
    y: int
    width: int
    height: int
    image_width: int
    image_height: int
    line_id: int = 0
    block_id: int = 0

    @property
    def box(self) -> BoundingBox:
        iw = max(self.image_width, 1)
        ih = max(self.image_height, 1)
        return BoundingBox(
            x=self.x / iw,
            y=self.y / ih,
            width=self.width / iw,
            height=self.height / ih,
        )


class OCRResult(BaseModel):
    full_text: str = ""
    average_confidence: float = 0.0
    image_width: int = 0
    image_height: int = 0
    words: list[OCRWord] = Field(default_factory=list)
    lines: list[str] = Field(default_factory=list)

    @property
    def confidence_level(self) -> ConfidenceLevel:
        return confidence_level(self.average_confidence)

    @property
    def has_useful_text(self) -> bool:
        cleaned = " ".join(self.full_text.split())
        return len(cleaned) >= 8 and len(self.words) >= 2
