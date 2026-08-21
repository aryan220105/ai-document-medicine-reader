from __future__ import annotations

import logging
import shutil
from collections import defaultdict
from pathlib import Path

import pytesseract
from PIL import Image

from app.config import Settings
from app.models.ocr import OCRResult, OCRWord

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

    def extract(self, image_path: str) -> OCRResult:
        image = Image.open(image_path)
        width, height = image.size
        lang = self._resolve_lang()
        data = pytesseract.image_to_data(
            image,
            lang=lang,
            output_type=pytesseract.Output.DICT,
        )
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
                conf = -1.0
            if conf < 0:
                continue
            word = OCRWord(
                id=len(words),
                text=text,
                confidence=conf,
                x=int(data["left"][index]),
                y=int(data["top"][index]),
                width=int(data["width"][index]),
                height=int(data["height"][index]),
                image_width=width,
                image_height=height,
                line_id=int(data.get("line_num", [0] * n)[index]),
                block_id=int(data.get("block_num", [0] * n)[index]),
            )
            words.append(word)
            confidences.append(conf)

        lines = self._group_lines(words)
        full_text = "\n".join(lines).strip()
        average = sum(confidences) / len(confidences) if confidences else 0.0
        return OCRResult(
            full_text=full_text,
            average_confidence=round(average, 2),
            image_width=width,
            image_height=height,
            words=words,
            lines=lines,
        )

    def _resolve_lang(self) -> str:
        requested = self.settings.tesseract_lang or "eng"
        try:
            available = set(pytesseract.get_languages(config=""))
        except Exception:
            logger.warning("Could not list Tesseract languages; using eng")
            return "eng"
        parts = [part.strip() for part in requested.replace("+", " ").split() if part.strip()]
        usable = [part for part in parts if part in available]
        if not usable:
            return "eng" if "eng" in available else (next(iter(available), "eng"))
        return "+".join(usable)

    @staticmethod
    def _group_lines(words: list[OCRWord]) -> list[str]:
        buckets: dict[tuple[int, int], list[OCRWord]] = defaultdict(list)
        for word in words:
            buckets[(word.block_id, word.line_id)].append(word)
        lines: list[str] = []
        for key in sorted(buckets):
            ordered = sorted(buckets[key], key=lambda item: item.x)
            line = " ".join(item.text for item in ordered).strip()
            if line:
                lines.append(line)
        return lines
