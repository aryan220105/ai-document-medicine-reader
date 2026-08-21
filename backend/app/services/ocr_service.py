from __future__ import annotations

from app.models.ocr import OCRResult
from app.providers.ocr.tesseract import TesseractOCRProvider


class OCRService:
    def __init__(self, provider: TesseractOCRProvider) -> None:
        self.provider = provider

    def available(self) -> bool:
        return self.provider.available()

    def extract(self, image_path: str) -> OCRResult:
        return self.provider.extract(image_path)
