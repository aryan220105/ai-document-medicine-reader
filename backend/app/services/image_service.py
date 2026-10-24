from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Indic and Arabic scripts carry their meaning in small marks -- vowel signs, nuqtas,
# dots above and below -- that disappear first when a page is downscaled. 1800 was enough
# for Latin and too tight for the rest.
MAX_OCR_DIMENSION = 2400

# A page boundary covers most of the frame and reaches all four edges. Anything smaller
# is an element inside the document -- usually a ruled table -- and cropping to it
# silently deletes the rest of the form.
MIN_DOCUMENT_AREA_RATIO = 0.60
EDGE_INSET_RATIO = 0.12
# Above this the image already *is* the page, so warping it would only resample the text.
FULL_PAGE_AREA_RATIO = 0.97


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

    def apply_exif(self, source_path: str) -> None:
        try:
            from PIL import Image, ImageOps

            with Image.open(source_path) as image:
                corrected = ImageOps.exif_transpose(image)
                if corrected is not None and corrected.size != image.size:
                    corrected.save(source_path)
        except Exception:
            logger.debug("EXIF orientation correction skipped")

    def preprocess(self, source_path: str, destination_path: str) -> PreprocessResult:
        self.apply_exif(source_path)
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
        """Find the page's own edge, for a photograph of a document on a background.

        Only the page edge. A form is full of large four-sided shapes -- every ruled table
        is one -- and cropping to one of those throws away the rest of the document. On a
        Kannada electoral form the two-column table won this contest and the processed
        page lost its title, its first three fields and its entire lower half, which then
        looked like a field-detection failure rather than a cropping one.

        So a candidate must behave like a page boundary: cover most of the image, and
        reach close to all four edges. An interior table satisfies neither.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        height, width = image.shape[:2]
        image_area = float(height * width)
        best = None
        best_area = 0.0
        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            area = cv2.contourArea(approx)
            if len(approx) != 4 or area <= best_area:
                continue
            if area < MIN_DOCUMENT_AREA_RATIO * image_area:
                continue
            x, y, w, h = cv2.boundingRect(approx)
            reaches_edges = (
                x <= EDGE_INSET_RATIO * width
                and y <= EDGE_INSET_RATIO * height
                and x + w >= (1.0 - EDGE_INSET_RATIO) * width
                and y + h >= (1.0 - EDGE_INSET_RATIO) * height
            )
            if not reaches_edges:
                continue
            if area > FULL_PAGE_AREA_RATIO * image_area:
                # Already a flat, full-bleed page: a rendered PDF, or a scan with no
                # visible margin. Warping it would only resample and blur the text.
                continue
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
        # A rendered or cleanly scanned page is already black ink on white paper.
        # Denoising and a second threshold break Urdu and Hindi strokes; Tesseract
        # reads the grayscale page itself far more accurately. Photographs of a
        # form on a desk are darker and still take the cleanup below.
        if float((gray > 200).mean()) > 0.85:
            return cv2.cvtColor(self._deskew(gray), cv2.COLOR_GRAY2BGR)
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
        angle = self._estimate_skew(gray)
        if abs(angle) < 0.2:
            return gray
        height, width = gray.shape[:2]
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        return cv2.warpAffine(gray, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    @staticmethod
    def _estimate_skew(gray: np.ndarray, max_angle: float = 15.0) -> float:
        """Projection-profile skew search: text rows and form lines produce the sharpest
        horizontal profile when the page is level. Scanned pages rarely contain pure white,
        so ink is isolated with a local threshold instead of a global one."""
        height, width = gray.shape[:2]
        scale = min(1.0, 900 / float(max(height, width)))
        small = cv2.resize(gray, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
        ink = cv2.adaptiveThreshold(small, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 15)
        if cv2.countNonZero(ink) < 50:
            return 0.0
        h, w = ink.shape[:2]
        center = (w / 2, h / 2)

        def score(angle: float) -> float:
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(ink, matrix, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
            profile = rotated.sum(axis=1, dtype=np.float64)
            return float(np.square(np.diff(profile)).sum())

        coarse = max(np.arange(-max_angle, max_angle + 0.01, 0.5), key=score)
        fine = max(np.arange(coarse - 0.5, coarse + 0.51, 0.1), key=score)
        return float(round(fine, 2))
