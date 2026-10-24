from __future__ import annotations

import logging
import unicodedata
from pathlib import Path

from PIL import Image

from app.models.common import PixelBoundingBox
from app.models.ocr import OCRResult, OCRWord
from app.providers.ocr.tesseract import TesseractOCRProvider
from app.utils.text_normalization import dominant_script

logger = logging.getLogger(__name__)

# A page whose file already contains this much real text is a digital form, not a scan
# with a stray header. Below this, the printed image is still the thing to read.
_MIN_EMBEDDED_WORDS = 20
_MIN_EMBEDDED_LETTERS = 80

def pdf_word_text(raw: str) -> str:
    """Printable text from one PDF word, with presentation forms folded to letters."""
    normalized = unicodedata.normalize("NFKC", str(raw))
    return "".join(char for char in normalized if char.isprintable()).strip()


_LANG_FOR_SCRIPT = {
    "devanagari": "hin",
    "kannada": "kan",
    "arabic": "urd",
    "latin": "eng",
}


class PdfService:
    def render_pages(self, source: Path, destination_dir: Path, max_pages: int) -> list[Path]:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PDF support requires PyMuPDF (pymupdf).") from exc
        document = fitz.open(source)
        if document.is_encrypted:
            document.close()
            raise ValueError("This PDF is encrypted. Please upload an unlocked copy.")
        if document.page_count < 1:
            document.close()
            raise ValueError("The PDF has no readable pages.")
        if document.page_count > max_pages:
            document.close()
            raise ValueError(f"Please upload a PDF with at most {max_pages} pages.")
        destination_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            path = destination_dir / f"page-{index}.png"
            pixmap.save(str(path))
            paths.append(path)
        document.close()
        return paths

    def read_embedded_text(
        self,
        source: Path,
        page_index: int,
        image_width: int,
        image_height: int,
    ) -> OCRResult | None:
        """Read the page's own text layer, in the processed image's pixel space.

        A digital form such as the Hindi enumeration sheet already stores every label
        correctly. OCR of the same page reorders vowel signs and invents captions, so
        when the file has a real text layer that layer is the reading to keep. A scan
        has no text layer and returns None, leaving OCR in charge.

        Coordinates are PDF points scaled onto the image the rest of the pipeline
        measures boxes against.
        """
        try:
            import fitz
        except ImportError:
            return None
        if image_width < 1 or image_height < 1:
            return None
        document = fitz.open(source)
        try:
            if page_index < 0 or page_index >= document.page_count:
                return None
            page = document[page_index]
            rect = page.rect
            if rect.width < 1 or rect.height < 1:
                return None
            scale_x = image_width / float(rect.width)
            scale_y = image_height / float(rect.height)
            words: list[OCRWord] = []
            letters = 0
            for x0, y0, x1, y1, raw, block_no, line_no, _word_no in page.get_text("words"):
                text = pdf_word_text(raw)
                # A colon is its own token in these PDFs. Dropping it makes
                # "Elector name :" look like a heading, so the row is never offered.
                if not any(ch.isalpha() for ch in text) and ":" not in text and "：" not in text:
                    continue
                letters += sum(1 for ch in text if ch.isalpha())
                words.append(
                    OCRWord(
                        id=f"p{page_index}-e{len(words)}",
                        text=text,
                        confidence=99.0,
                        page_index=page_index,
                        pixel=PixelBoundingBox(
                            x=max(0, int(x0 * scale_x)),
                            y=max(0, int(y0 * scale_y)),
                            width=max(1, int((x1 - x0) * scale_x)),
                            height=max(1, int((y1 - y0) * scale_y)),
                            image_width=image_width,
                            image_height=image_height,
                            page_index=page_index,
                        ),
                        line_id=int(line_no),
                        block_id=int(block_no),
                        reading_index=len(words),
                    )
                )
        finally:
            document.close()
        if len(words) < _MIN_EMBEDDED_WORDS or letters < _MIN_EMBEDDED_LETTERS:
            return None
        # A broken font encoding writes digits and "#" inside Devanagari words
        # ("पि3छले", "स्थानांतरि#त"). The rendered page is readable, so OCR of it
        # is the reading to keep.
        if self._devanagari_layer_is_misencoded(words):
            logger.info("PDF text layer page=%s is misencoded; using OCR", page_index)
            return None
        lines = TesseractOCRProvider._group_lines(words)
        full_text = "\n".join(line.text for line in lines).strip()
        script = dominant_script(full_text)
        lang = _LANG_FOR_SCRIPT.get(script, "eng")
        logger.info(
            "PDF text layer page=%s words=%s script=%s",
            page_index,
            len(words),
            script,
        )
        return OCRResult(
            page_index=page_index,
            full_text=full_text,
            average_confidence=99.0,
            image_width=image_width,
            image_height=image_height,
            words=words,
            lines=lines,
            script=script,
            languages_used=[lang] if lang == "eng" else [lang, "eng"],
            rtl=script == "arabic",
        )

    @staticmethod
    def _devanagari_layer_is_misencoded(words: list[OCRWord]) -> bool:
        bad = 0
        for word in words:
            text = word.text
            has_devanagari = any("\u0900" <= char <= "\u097f" for char in text)
            has_junk = any(char.isdigit() or char in "#><=" for char in text)
            if has_devanagari and has_junk:
                bad += 1
        return bad >= 8

    def write_pdf(self, images: list[Path], destination: Path) -> None:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PDF support requires PyMuPDF (pymupdf).") from exc
        document = fitz.open()
        for image_path in images:
            image = Image.open(image_path)
            width, height = image.size
            page = document.new_page(width=width, height=height)
            page.insert_image(page.rect, filename=str(image_path))
        destination.parent.mkdir(parents=True, exist_ok=True)
        document.save(destination)
        document.close()
