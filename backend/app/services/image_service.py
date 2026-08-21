from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

MAX_OCR_DIMENSION = 1800


@dataclass
class PreprocessResult:
    processed_path: str
    detection_succeeded: bool
    original_width: int
    original_height: int
    processed_width: int
    processed_height: int


class ImageService:
    def load(self, path: str) -> np.ndarray:
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            image = cv2.imread(path)
        if image is None:
            raise ValueError("The image could not be read. Please upload a PNG, JPG, JPEG, or WEBP file.")
        return image

    def save(self, image: np.ndarray, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        extension = Path(path).suffix.lower() or ".png"
        success, encoded = cv2.imencode(extension, image)
        if not success:
            success, encoded = cv2.imencode(".png", image)
            path = str(Path(path).with_suffix(".png"))
        encoded.tofile(path)

    def preprocess(self, source_path: str, destination_path: str) -> PreprocessResult:
        original = self.load(source_path)
        original_height, original_width = original.shape[:2]
        working = self._resize_if_needed(original)
        detection_succeeded = False
        warped = working
        try:
            contour = self._largest_document_contour(working)
            if contour is not None:
                warped = self._perspective_transform(working, contour)
                detection_succeeded = True
        except Exception:
            logger.exception("Document contour detection failed; using original image")
            warped = working
            detection_succeeded = False

        enhanced = self._enhance_for_ocr(warped)
        self.save(enhanced, destination_path)
        processed = self.load(destination_path)
        processed_height, processed_width = processed.shape[:2]
        return PreprocessResult(
            processed_path=destination_path,
            detection_succeeded=detection_succeeded,
            original_width=original_width,
            original_height=original_height,
            processed_width=processed_width,
            processed_height=processed_height,
        )

    def _resize_if_needed(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        longest = max(height, width)
        if longest <= MAX_OCR_DIMENSION:
            return image
        scale = MAX_OCR_DIMENSION / float(longest)
        return cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)

    def _largest_document_contour(self, image: np.ndarray) -> np.ndarray | None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        height, width = image.shape[:2]
        image_area = height * width
        best = None
        best_area = 0.0
        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            area = cv2.contourArea(approx)
            if len(approx) == 4 and area > best_area and area > 0.18 * image_area:
                best = approx
                best_area = area
        return best

    def _order_points(self, points: np.ndarray) -> np.ndarray:
        pts = points.reshape(4, 2).astype(np.float32)
        sums = pts.sum(axis=1)
        diffs = np.diff(pts, axis=1).flatten()
        ordered = np.zeros((4, 2), dtype=np.float32)
        ordered[0] = pts[np.argmin(sums)]
        ordered[2] = pts[np.argmax(sums)]
        ordered[1] = pts[np.argmin(diffs)]
        ordered[3] = pts[np.argmax(diffs)]
        return ordered

    def _perspective_transform(self, image: np.ndarray, contour: np.ndarray) -> np.ndarray:
        ordered = self._order_points(contour)
        width_a = np.linalg.norm(ordered[2] - ordered[3])
        width_b = np.linalg.norm(ordered[1] - ordered[0])
        height_a = np.linalg.norm(ordered[1] - ordered[2])
        height_b = np.linalg.norm(ordered[0] - ordered[3])
        max_width = max(int(width_a), int(width_b), 1)
        max_height = max(int(height_a), int(height_b), 1)
        destination = np.array(
            [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(ordered, destination)
        return cv2.warpPerspective(image, matrix, (max_width, max_height))

    def _enhance_for_ocr(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, None, 15, 7, 21)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrasted = clahe.apply(denoised)
        deskewed = self._deskew(contrasted)
        binary = cv2.adaptiveThreshold(
            deskewed,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    def _deskew(self, gray: np.ndarray) -> np.ndarray:
        inverted = cv2.bitwise_not(gray)
        coords = np.column_stack(np.where(inverted > 0))
        if coords.size == 0:
            return gray
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.4 or abs(angle) > 15:
            return gray
        height, width = gray.shape[:2]
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        return cv2.warpAffine(gray, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
