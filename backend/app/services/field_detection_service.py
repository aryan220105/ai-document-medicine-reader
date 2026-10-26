from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.config import Settings
from app.models.common import FieldType, PixelBoundingBox
from app.models.fields import DetectedField
from app.utils.bounding_boxes import iou, normalize_box


@dataclass
class DetectionCandidate:
    field_type: FieldType
    pixel: PixelBoundingBox
    confidence: float
    reasons: list[str]
    line_y: int | None = None


class FieldDetectionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def detect(self, image_path: str, page_index: int) -> list[DetectedField]:
        image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            image = cv2.imread(image_path)
        if image is None:
            return []
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        boxes = self._boxes(gray, width, height, page_index)
        underlines = self._drop_box_edges(self._underlines(gray, width, height, page_index), boxes)
        candidates = boxes + underlines + self._drop_glyph_rows(self._check_marks(gray, width, height, page_index))
        merged = self._merge(self._prune(candidates, width, height))
        fields: list[DetectedField] = []
        for index, candidate in enumerate(merged):
            fields.append(
                DetectedField(
                    id=f"p{page_index}-f{index}",
                    page_index=page_index,
                    label="",
                    field_type=candidate.field_type,
                    input_box=normalize_box(candidate.pixel),
                    confidence=candidate.confidence,
                    confidence_reasons=candidate.reasons,
                )
            )
        return fields

    def detect_marks(self, image_path: str, page_index: int) -> list[DetectedField]:
        """Only the tick boxes and radio buttons.

        Exposed separately because a page analysed as a table grid still needs its
        checkboxes, and they are found by a different measurement than the cells are.
        """
        image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            image = cv2.imread(image_path)
        if image is None:
            return []
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        marks = self._drop_glyph_rows(self._check_marks(gray, width, height, page_index))
        merged = self._merge(self._prune(marks, width, height))
        return [
            DetectedField(
                id=f"p{page_index}-m{index}",
                page_index=page_index,
                label="",
                field_type=candidate.field_type,
                input_box=normalize_box(candidate.pixel),
                confidence=candidate.confidence,
                confidence_reasons=candidate.reasons,
            )
            for index, candidate in enumerate(merged)
        ]

    def _prune(self, candidates: list[DetectionCandidate], width: int, height: int) -> list[DetectionCandidate]:
        kept: list[DetectionCandidate] = []
        for candidate in candidates:
            w, h = candidate.pixel.width, candidate.pixel.height
            if candidate.field_type in {FieldType.CHECKBOX, FieldType.RADIO}:
                if 10 <= w <= 36 and 10 <= h <= 36:
                    kept.append(candidate)
                continue
            if w < max(80, int(width * 0.12)) or h < 16 or h > int(height * 0.22):
                continue
            kept.append(candidate)
        return kept

    def _boxes(self, gray: np.ndarray, width: int, height: int, page_index: int) -> list[DetectionCandidate]:
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        binary = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 9)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        results: list[DetectionCandidate] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w < 40 or h < 16:
                continue
            if w > width * 0.95 or h > height * 0.4:
                continue
            area = w * h
            if area < 800 or area > width * height * 0.35:
                continue
            aspect = w / max(h, 1)
            if aspect < 1.4:
                continue
            if not self._rectangular_frame(binary, x, y, w, h):
                continue
            pixel = PixelBoundingBox(x=x, y=y, width=w, height=h, image_width=width, image_height=height, page_index=page_index)
            field_type = FieldType.MULTILINE if h > 48 else FieldType.TEXT
            results.append(DetectionCandidate(field_type, pixel, 0.72, ["rectangular_box"]))
        return results

    def _underlines(self, gray: np.ndarray, width: int, height: int, page_index: int) -> list[DetectionCandidate]:
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 8)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (90, 1))
        lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        results: list[DetectionCandidate] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w < width * 0.18 or h > 8:
                continue
            box_y = max(0, y - 28)
            pixel = PixelBoundingBox(
                x=x,
                y=box_y,
                width=w,
                height=min(36, height - box_y),
                image_width=width,
                image_height=height,
                page_index=page_index,
            )
            results.append(DetectionCandidate(FieldType.TEXT, pixel, 0.64, ["underline"], line_y=y + h // 2))
        return results

    def _check_marks(self, gray: np.ndarray, width: int, height: int, page_index: int) -> list[DetectionCandidate]:
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 7)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        results: list[DetectionCandidate] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w < 8 or h < 8 or w > 40 or h > 40:
                continue
            aspect = w / max(h, 1)
            if aspect < 0.65 or aspect > 1.4:
                continue
            fill = cv2.contourArea(contour) / max(w * h, 1)
            if fill < 0.08 or fill > 0.95:
                continue
            if not self._hollow_mark(gray, x, y, w, h):
                continue
            pixel = PixelBoundingBox(x=x, y=y, width=w, height=h, image_width=width, image_height=height, page_index=page_index)
            field_type = FieldType.RADIO if self._empty_corners(gray, x, y, w, h) else FieldType.CHECKBOX
            results.append(DetectionCandidate(field_type, pixel, 0.7, [field_type.value]))
        return results

    @staticmethod
    def _rectangular_frame(binary: np.ndarray, x: int, y: int, w: int, h: int) -> bool:
        """A drawn input box has ink along all four sides; a run of merged text glyphs does not."""
        roi = binary[y : y + h, x : x + w] > 0
        band = max(3, min(w, h) // 8)
        coverage = (
            roi[:band, :].any(axis=0).mean(),
            roi[-band:, :].any(axis=0).mean(),
            roi[:, :band].any(axis=1).mean(),
            roi[:, -band:].any(axis=1).mean(),
        )
        return min(coverage) >= 0.8

    @staticmethod
    def _drop_box_edges(underlines: list[DetectionCandidate], boxes: list[DetectionCandidate]) -> list[DetectionCandidate]:
        """Horizontal-line detection also fires on the top and bottom edges of rectangles."""
        kept: list[DetectionCandidate] = []
        for line in underlines:
            line_y = line.line_y if line.line_y is not None else line.pixel.y + line.pixel.height
            on_edge = False
            for box in boxes:
                b = box.pixel
                overlap = min(line.pixel.x + line.pixel.width, b.x + b.width) - max(line.pixel.x, b.x)
                if overlap < min(line.pixel.width, b.width) * 0.8:
                    continue
                if abs(line_y - b.y) <= 6 or abs(line_y - (b.y + b.height)) <= 6:
                    on_edge = True
                    break
            if not on_edge:
                kept.append(line)
        return kept

    @staticmethod
    def _empty_corners(gray: np.ndarray, x: int, y: int, w: int, h: int) -> bool:
        """A circle leaves its bounding-box corners blank; a square has ink there. This is
        steadier than contour circularity once a scan has been rotated and re-thresholded."""
        size = max(2, min(w, h) // 6)
        roi = gray[y : y + h, x : x + w] < 150
        corners = (roi[:size, :size], roi[:size, -size:], roi[-size:, :size], roi[-size:, -size:])
        return float(np.mean([corner.mean() for corner in corners])) < 0.25

    @staticmethod
    def _hollow_mark(gray: np.ndarray, x: int, y: int, w: int, h: int) -> bool:
        roi = gray[y : y + h, x : x + w]
        if roi.size == 0 or w < 8 or h < 8:
            return False
        inset = max(2, min(w, h) // 4)
        center = roi[inset : h - inset, inset : w - inset]
        if center.size == 0 or float(center.mean()) < 180:
            return False
        # Look for ink within a band along each side rather than on the exact outer
        # pixel row: rotated or noisy scans shift the stroke inward by a pixel or two,
        # and a radio circle only touches its bounding box at four tangent points.
        ink = roi < 150
        band = max(2, min(w, h) // 5)
        coverage = [
            float(ink[:band, :].any(axis=0).mean()),
            float(ink[-band:, :].any(axis=0).mean()),
            float(ink[:, :band].any(axis=1).mean()),
            float(ink[:, -band:].any(axis=1).mean()),
        ]
        return min(coverage) >= 0.45 and sum(coverage) / 4 >= 0.5

    @staticmethod
    def _drop_glyph_rows(candidates: list[DetectionCandidate]) -> list[DetectionCandidate]:
        kept: list[DetectionCandidate] = []
        for candidate in candidates:
            cy = candidate.pixel.y + candidate.pixel.height / 2
            neighbors = 0
            for other in candidates:
                oy = other.pixel.y + other.pixel.height / 2
                if abs(oy - cy) <= max(candidate.pixel.height, 10) and abs(other.pixel.x - candidate.pixel.x) <= 100:
                    neighbors += 1
            if neighbors >= 4:
                continue
            kept.append(candidate)
        return kept

    @staticmethod
    def _same_region(current: PixelBoundingBox, other: PixelBoundingBox, threshold: float) -> bool:
        if iou(current, other) >= threshold:
            return True
        ax2, ay2 = current.x + current.width, current.y + current.height
        bx2, by2 = other.x + other.width, other.y + other.height
        overlap_x = max(0, min(ax2, bx2) - max(current.x, other.x))
        if overlap_x <= 0:
            return False
        shared = overlap_x / max(min(current.width, other.width), 1)
        # Measure vertical agreement against the smaller box so a tall box (e.g. an
        # address area) cannot absorb a separate field stacked directly below it.
        overlap_y = min(ay2, by2) - max(current.y, other.y)
        shared_y = overlap_y / max(min(current.height, other.height), 1)
        return shared >= 0.55 and shared_y >= 0.5

    def _merge(self, candidates: list[DetectionCandidate]) -> list[DetectionCandidate]:
        remaining = sorted(candidates, key=lambda item: item.confidence, reverse=True)
        merged: list[DetectionCandidate] = []
        threshold = self.settings.field_iou_merge
        while remaining:
            current = remaining.pop(0)
            kept: list[DetectionCandidate] = []
            for other in remaining:
                if self._same_region(current.pixel, other.pixel, threshold):
                    current.reasons = list(dict.fromkeys(current.reasons + other.reasons))
                    current.confidence = max(current.confidence, other.confidence)
                else:
                    kept.append(other)
            merged.append(current)
            remaining = kept
        return merged
