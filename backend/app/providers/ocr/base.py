from __future__ import annotations

from typing import Protocol

from app.models.ocr import OCRResult


class OCRProvider(Protocol):
    def extract(self, image_path: str) -> OCRResult:
        ...

    def available(self) -> bool:
        ...
