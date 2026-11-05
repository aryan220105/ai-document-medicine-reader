from app.models.ocr import OCRResult
from app.providers.ocr.tesseract import TesseractOCRProvider


class OCRService:
    def __init__(self, provider: TesseractOCRProvider) -> None:
        self.provider = provider

    def available(self) -> bool:
        return self.provider.available()

    def extract(self, image_path: str, page_index: int = 0) -> OCRResult:
        return self.provider.extract(image_path, page_index=page_index)

    def read_region(
        self,
        image_path: str,
        x: float,
        y: float,
        width: float,
        height: float,
        lang: str | None = None,
        psm: int = 7,
    ) -> str:
        """Read one normalized region of the page as a single line.

        Used to recover a printed label that whole-page segmentation skipped.
        """
        return self.provider.read_region(image_path, x, y, width, height, lang=lang, psm=psm)
