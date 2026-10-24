from __future__ import annotations

import logging
import os
import shutil
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.config import BACKEND_DIR, Settings
from app.models.common import PixelBoundingBox
from app.models.ocr import OCRLine, OCRResult, OCRWord
from app.utils.bounding_boxes import iou, union_boxes
from app.utils.text_normalization import dominant_script

logger = logging.getLogger(__name__)

# Tesseract's OSD script names mapped to the traineddata that reads them.
SCRIPT_LANGS = {
    "Devanagari": "hin",
    "Kannada": "kan",
    "Arabic": "urd",
    "Latin": "eng",
}

SCRIPT_FOR_LANG = {
    "hin": "devanagari",
    "kan": "kannada",
    "urd": "arabic",
    "eng": "latin",
}

RTL_LANGS = {"urd", "ara", "fas"}

# A reading scoring below this is treated as suspect and retried with the full language
# set. The score is mean word confidence scaled by how much text was found, so it is low
# both when little was read and when what was read was read badly.
WEAK_READING = 40.0

# Script detection on a Latin-only page is unreliable (it has been seen to answer
# "Cyrillic" at 0.12 confidence), so a detection is only acted on when it names a
# non-Latin script with real confidence behind it.
MIN_SCRIPT_CONFIDENCE = 2.0

# Thresholds for merging a second reading of the page into the first.
MERGE_CONFIDENCE_FLOOR = 45.0
MERGE_OVERLAP = 0.3


class TesseractOCRProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        # Hindi, Kannada, and Urdu models live beside the backend when the system
        # install only has English. Tesseract looks for traineddata inside this directory.
        bundled = BACKEND_DIR / "tessdata"
        if (bundled / "hin.traineddata").is_file() and (bundled / "kan.traineddata").is_file() and (bundled / "urd.traineddata").is_file():
            os.environ["TESSDATA_PREFIX"] = str(bundled)

    def available(self) -> bool:
        configured = (self.settings.tesseract_cmd or "").strip()
        if configured:
            return Path(configured).exists()
        return shutil.which("tesseract") is not None

    def extract(self, image_path: str, page_index: int = 0) -> OCRResult:
        """Read a page, choosing the Tesseract models and the image treatment to read with.

        Three decisions are made here, each because a single fixed choice measurably loses
        text on one of the four supported scripts:

        1. *Which language models.* Loading every installed script at once makes the engine
           choose between four alphabets per glyph and badly corrupts Latin text ("FORM"
           came back as Arabic-Indic digits). Script detection is accurate on Devanagari,
           Kannada, and Arabic pages but near-useless on a Latin one, so a confident
           non-Latin detection picks that one model plus English, and anything else starts
           with English alone.
        2. *Whether that reading was good enough.* If it scores poorly the full configured
           set is tried and the better reading wins.
        3. *Which image.* Erasing the form's rules helps Tesseract's layout analysis find
           labels wedged against a box border, but it also costs text on crisp scans. So
           the page is read both with and without the rules removed and the two word sets
           are merged, which recovers labels either pass alone would have missed.
        """
        image = Image.open(image_path)
        width, height = image.size
        prepared = self._remove_rulings(image)

        lang = self._resolve_lang(prepared)
        data = self._read(prepared, lang)
        score = self._score(data)

        fallback = self._all_languages()
        if score < WEAK_READING and fallback and fallback != lang:
            alternative = self._read(prepared, fallback)
            if self._score(alternative) > score:
                logger.debug("OCR fell back from %s to %s", lang, fallback)
                lang, data, score = fallback, alternative, self._score(alternative)

        words = self._words(data, page_index, width, height)
        # Second view of the same page, rules intact. Only words that do not already have
        # a reading at that position are taken, so this adds coverage without duplicating.
        plain = self._words(self._read(image, lang), page_index, width, height)
        words = self._merge_words(words, plain)

        lines = self._group_lines(words)
        full_text = "\n".join(line.text for line in lines).strip()
        confidences = [word.confidence for word in words if word.confidence > 0]
        average = sum(confidences) / len(confidences) if confidences else 0.0
        script = dominant_script(full_text)
        return OCRResult(
            page_index=page_index,
            full_text=full_text,
            average_confidence=round(average, 2),
            image_width=width,
            image_height=height,
            words=words,
            lines=lines,
            script=script,
            languages_used=[part for part in lang.split("+") if part],
            rtl=script == "arabic",
        )

    @staticmethod
    def _words(data: dict, page_index: int, width: int, height: int) -> list[OCRWord]:
        words: list[OCRWord] = []
        count = len(data.get("text", []))
        for index in range(count):
            text = (data["text"][index] or "").strip()
            if not text:
                continue
            try:
                conf = float(data["conf"][index])
            except (TypeError, ValueError):
                conf = 0.0
            words.append(
                OCRWord(
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
                    line_id=int(data.get("line_num", [0] * count)[index]),
                    block_id=int(data.get("block_num", [0] * count)[index]),
                )
            )
        return words

    @staticmethod
    def _merge_words(primary: list[OCRWord], extra: list[OCRWord]) -> list[OCRWord]:
        """Add words from a second reading where the first found nothing.

        A word is only added when no accepted word already covers that part of the page,
        so the two readings cannot produce two overlapping transcriptions of the same ink.
        Low-confidence additions are refused: a second opinion is worth having only when
        the engine is reasonably sure of it.
        """
        merged = list(primary)
        for candidate in extra:
            if candidate.confidence < MERGE_CONFIDENCE_FLOOR:
                continue
            if any(iou(candidate.box, accepted.box) >= MERGE_OVERLAP for accepted in merged):
                continue
            merged.append(candidate.model_copy(update={"id": f"{candidate.id}-b"}))
        merged.sort(key=lambda item: (item.pixel.y, item.pixel.x))
        return merged

    @staticmethod
    def _remove_rulings(image: Image.Image) -> Image.Image:
        """Erase long horizontal/vertical form lines before OCR.

        Box borders next to a label (especially broken, dashed-looking borders on noisy
        scans) make Tesseract's layout analysis discard the label as non-text. Geometry is
        unchanged, so word coordinates still line up with the processed page.

        What counts as a "line" has to be judged per connected component, not by a fixed
        kernel length. Devanagari joins the letters of a word under one continuous
        headline (shirorekha) and Urdu joins them along a continuous baseline, both of
        which a short kernel happily mistakes for a rule: an earlier version of this
        erased the labels for father's name, mobile number, and signature outright. A real
        rule is both far longer than a word and only a couple of pixels thick, so each
        candidate is measured and only genuinely long, thin runs are removed.
        """
        try:
            gray = np.array(image.convert("L"))
            height, width = gray.shape[:2]
            ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)

            horizontal = cv2.morphologyEx(
                ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(60, width // 10), 1))
            )
            vertical = cv2.morphologyEx(
                ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(30, height // 50)))
            )

            keep = np.zeros_like(ink)
            TesseractOCRProvider._keep_lines(
                horizontal, keep, min_long=max(60, width // 6), max_thick=max(4, height // 400), axis="h"
            )
            TesseractOCRProvider._keep_lines(
                vertical, keep, min_long=max(30, height // 40), max_thick=max(4, width // 400), axis="v"
            )
            if not keep.any():
                return Image.fromarray(gray)
            mask = cv2.dilate(keep, np.ones((3, 3), np.uint8))
            gray[mask > 0] = 255
            return Image.fromarray(gray)
        except Exception:
            logger.debug("Ruling-line removal skipped")
            return image

    @staticmethod
    def _keep_lines(candidates: np.ndarray, keep: np.ndarray, min_long: int, max_thick: int, axis: str) -> None:
        """Copy only the long, thin components of `candidates` into `keep`."""
        count, labels, stats, _ = cv2.connectedComponentsWithStats(candidates, connectivity=8)
        for index in range(1, count):
            w = int(stats[index, cv2.CC_STAT_WIDTH])
            h = int(stats[index, cv2.CC_STAT_HEIGHT])
            long_side, thin_side = (w, h) if axis == "h" else (h, w)
            if long_side >= min_long and thin_side <= max_thick:
                keep[labels == index] = 255

    @staticmethod
    def _read(image: Image.Image, lang: str) -> dict:
        return pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

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
        """Read one small region of the page as a single line of text.

        Whole-page segmentation sometimes refuses to see a label at all: a short caption
        beside a large empty box gets classified as part of a graphic and never reaches
        the word list, which was observed on crisp Kannada and Urdu renders where the very
        same words read correctly in isolation. Cropping to where the label must be and
        asking for one line (psm 7) recovers it. The crop is enlarged first, because the
        engine is markedly more accurate on larger glyphs.

        Coordinates are normalized. Returns an empty string when nothing readable is there.
        """
        try:
            image = Image.open(image_path)
            page_w, page_h = image.size
            left = max(0, int(x * page_w))
            top = max(0, int(y * page_h))
            right = min(page_w, int((x + width) * page_w))
            bottom = min(page_h, int((y + height) * page_h))
            if right - left < 12 or bottom - top < 8:
                return ""
            crop = image.crop((left, top, right, bottom)).convert("L")
            crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
            text = pytesseract.image_to_string(
                crop, lang=lang or self._all_languages(), config=f"--psm {int(psm)}"
            )
            return " ".join(text.split()).strip()
        except Exception:
            logger.debug("Region re-read failed")
            return ""

    @staticmethod
    def _score(data: dict) -> float:
        """How well a reading went: mean confidence of real words, damped when the page
        yielded very few words at all."""
        confidences = []
        for index, text in enumerate(data.get("text", [])):
            if not (text or "").strip():
                continue
            try:
                value = float(data["conf"][index])
            except (TypeError, ValueError, IndexError):
                continue
            if value >= 0:
                confidences.append(value)
        if not confidences:
            return 0.0
        mean = sum(confidences) / len(confidences)
        return mean * min(1.0, len(confidences) / 12)

    def _all_languages(self) -> str:
        try:
            available = set(pytesseract.get_languages(config=""))
        except Exception:
            return "eng"
        parts = [
            part.strip()
            for part in (self.settings.tesseract_lang or "eng").replace("+", " ").split()
            if part.strip()
        ]
        usable = [part for part in parts if part in available]
        return "+".join(usable) if usable else "eng"

    def _resolve_lang(self, image: Image.Image | None = None) -> str:
        """Pick the Tesseract models to read this page with.

        Loading every installed script at once is both slow and less accurate: the engine
        has to choose between four alphabets for every glyph. So the page's script is
        detected first and only that model plus English is loaded -- English always, because
        regional forms routinely print English headings and Latin digits alongside the
        regional text.
        """
        try:
            available = set(pytesseract.get_languages(config=""))
        except Exception:
            return "eng"
        requested = [
            part.strip()
            for part in (self.settings.tesseract_lang or "eng").replace("+", " ").split()
            if part.strip()
        ]
        usable = [part for part in requested if part in available]
        if not usable:
            return "eng"

        detected = self._detect_script(image) if image is not None else None
        preferred = SCRIPT_LANGS.get(detected or "")
        if preferred and preferred != "eng" and preferred in usable:
            ordered = [preferred] + (["eng"] if "eng" in usable else [])
            logger.debug("OCR script=%s lang=%s", detected, "+".join(ordered))
            return "+".join(ordered)
        # No trustworthy detection: start with English alone rather than every installed
        # script, and let the caller's quality check decide whether to widen.
        return "eng" if "eng" in usable else "+".join(usable)

    def _detect_script(self, image: Image.Image) -> str | None:
        """Ask Tesseract's orientation-and-script model which alphabet this page uses.

        Returns None when the model is unavailable or unsure, in which case the caller
        falls back to the full configured language list rather than guessing.
        """
        try:
            osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
        except Exception:
            logger.debug("Script detection unavailable; using configured languages")
            return None
        script = osd.get("script")
        confidence = float(osd.get("script_conf", 0) or 0)
        if not script or confidence < MIN_SCRIPT_CONFIDENCE:
            return None
        return str(script)

    def script_of(self, image_path: str) -> str:
        """Dominant script of a page, for callers that only need the script."""
        try:
            detected = self._detect_script(Image.open(image_path))
        except Exception:
            return "unknown"
        if not detected:
            return "unknown"
        return SCRIPT_FOR_LANG.get(SCRIPT_LANGS.get(detected, ""), "unknown")

    @staticmethod
    def _group_lines(words: list[OCRWord]) -> list[OCRLine]:
        buckets: dict[tuple[int, int], list[OCRWord]] = defaultdict(list)
        for word in words:
            buckets[(word.block_id, word.line_id)].append(word)
        lines: list[OCRLine] = []
        for key in sorted(buckets):
            words_in_line = buckets[key]
            # Order each line the way it is read, not the way it sits on screen. Tesseract
            # gives Urdu words their true coordinates, so ascending x is visual order --
            # the reverse of reading order for a right-to-left script, which would leave
            # every Urdu line in `full_text` backwards.
            if all(item.reading_index is not None for item in words_in_line):
                ordered = sorted(words_in_line, key=lambda item: item.reading_index or 0)
            else:
                line_rtl = dominant_script(" ".join(item.text for item in words_in_line)) == "arabic"
                ordered = sorted(words_in_line, key=lambda item: item.pixel.x, reverse=line_rtl)
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
