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
        candidates = (
            self._boxes(gray, width, height, page_index)
            + self._underlines(gray, width, height, page_index)
            + self._check_marks(gray, width, height, page_index)
        )
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
            results.append(DetectionCandidate(FieldType.TEXT, pixel, 0.64, ["underline"]))
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
            pixel = PixelBoundingBox(x=x, y=y, width=w, height=h, image_width=width, image_height=height, page_index=page_index)
            circularity = 4 * np.pi * cv2.contourArea(contour) / max((cv2.arcLength(contour, True) ** 2), 1)
            field_type = FieldType.RADIO if circularity > 0.65 else FieldType.CHECKBOX
            results.append(DetectionCandidate(field_type, pixel, 0.7, [field_type.value]))
        return results

    def _merge(self, candidates: list[DetectionCandidate]) -> list[DetectionCandidate]:
        remaining = sorted(candidates, key=lambda item: item.confidence, reverse=True)
        merged: list[DetectionCandidate] = []
        threshold = self.settings.field_iou_merge
        while remaining:
            current = remaining.pop(0)
            kept: list[DetectionCandidate] = []
            for other in remaining:
                if iou(current.pixel, other.pixel) >= threshold:
                    current.reasons = list(dict.fromkeys(current.reasons + other.reasons))
                    current.confidence = max(current.confidence, other.confidence)
                else:
                    kept.append(other)
            merged.append(current)
            remaining = kept
        return merged
