from __future__ import annotations

import logging
import shutil
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.config import Settings
from app.models.common import PixelBoundingBox
from app.models.ocr import OCRLine, OCRResult, OCRWord
from app.utils.bounding_boxes import union_boxes

logger = logging.getLogger(__name__)


class TesseractOCRProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    def available(self) -> bool:
        configured = (self.settings.tesseract_cmd or "").strip()
        if configured:
            return Path(configured).exists()
        return shutil.which("tesseract") is not None

    def extract(self, image_path: str, page_index: int = 0) -> OCRResult:
        image = Image.open(image_path)
        width, height = image.size
        lang = self._resolve_lang()
        data = pytesseract.image_to_data(self._remove_rulings(image), lang=lang, output_type=pytesseract.Output.DICT)
        words: list[OCRWord] = []
        confidences: list[float] = []
        n = len(data.get("text", []))
        for index in range(n):
            text = (data["text"][index] or "").strip()
            if not text:
                continue
            try:
                conf = float(data["conf"][index])
            except (TypeError, ValueError):
                conf = 0.0
            word = OCRWord(
                id=f"p{page_index}-w{len(words)}",
                text=text,
                confidence=max(conf, 0.0),
                page_index=page_index,
                pixel=PixelBoundingBox(
                    x=int(data["left"][index]),
                    y=int(data["top"][index]),
                    width=int(data["width"][index]),
                    height=int(data["height"][index]),
                    image_width=width,
                    image_height=height,
                    page_index=page_index,
                ),
                line_id=int(data.get("line_num", [0] * n)[index]),
                block_id=int(data.get("block_num", [0] * n)[index]),
            )
            words.append(word)
            if conf >= 0:
                confidences.append(conf)
        lines = self._group_lines(words)
        full_text = "\n".join(line.text for line in lines).strip()
        average = sum(confidences) / len(confidences) if confidences else 0.0
        return OCRResult(
            page_index=page_index,
            full_text=full_text,
            average_confidence=round(average, 2),
            image_width=width,
            image_height=height,
            words=words,
            lines=lines,
        )

    @staticmethod
    def _remove_rulings(image: Image.Image) -> Image.Image:
        """Erase long horizontal/vertical form lines before OCR. Box borders next to a
        label (especially broken, dashed-looking borders on noisy scans) make Tesseract's
        layout analysis discard the label as non-text. Geometry is unchanged, so word
        coordinates still line up with the processed page."""
        try:
            gray = np.array(image.convert("L"))
            height, width = gray.shape[:2]
            ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
            horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, width // 30), 1)))
            vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(40, height // 45))))
            mask = cv2.dilate(cv2.bitwise_or(horizontal, vertical), np.ones((5, 5), np.uint8))
            gray[mask > 0] = 255
            return Image.fromarray(gray)
        except Exception:
            logger.debug("Ruling-line removal skipped")
            return image

    def _resolve_lang(self) -> str:
        requested = self.settings.tesseract_lang or "eng"
        try:
            available = set(pytesseract.get_languages(config=""))
        except Exception:
            return "eng"
        parts = [part.strip() for part in requested.replace("+", " ").split() if part.strip()]
        usable = [part for part in parts if part in available]
        return "+".join(usable) if usable else ("eng" if "eng" in available else "eng")

    @staticmethod
    def _group_lines(words: list[OCRWord]) -> list[OCRLine]:
        buckets: dict[tuple[int, int], list[OCRWord]] = defaultdict(list)
        for word in words:
            buckets[(word.block_id, word.line_id)].append(word)
        lines: list[OCRLine] = []
        for key in sorted(buckets):
            ordered = sorted(buckets[key], key=lambda item: item.pixel.x)
            text = " ".join(item.text for item in ordered).strip()
            if not text:
                continue
            lines.append(
                OCRLine(
                    id=len(lines),
                    text=text,
                    word_ids=[item.id for item in ordered],
                    box=union_boxes([item.box for item in ordered], label=text),
                )
            )
        return lines
