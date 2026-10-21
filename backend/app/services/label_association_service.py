from __future__ import annotations

import re

from app.models.common import FieldType
from app.models.fields import DetectedField, FieldOption
from app.models.ocr import OCRResult, OCRWord
from app.utils.bounding_boxes import iou
from app.utils.text_normalization import fold

SIGNATURE_TERMS = ("signature", "applicant signature", "sign here", "हस्ताक्षर", "ಸಹಿ")
DATE_TERMS = ("date of birth", "dob", "date", "दिनांक", "ದಿನಾಂಕ")
ADDRESS_TERMS = ("address", "residential address", "पता", "ವಿಳಾಸ")
OFFICE_USE_TERMS = ("office use", "official use", "for office", "कार्यालय उपयोग", "ಕಚೇರಿ ಬಳಕೆ")


class LabelAssociationService:
    def associate(self, fields: list[DetectedField], ocr: OCRResult) -> list[DetectedField]:
        used: set[str] = set()
        # Letter glyphs ("O", "D") can pass as checkbox/radio candidates; drop them before
        # labelling so they cannot claim the real labels of neighbouring fields.
        fields = [field for field in fields if not self._mark_inside_word(field, ocr)]
        marks = [field for field in fields if field.field_type in {FieldType.CHECKBOX, FieldType.RADIO}]
        self._label_marks(marks, ocr.words, used)
        for field in fields:
            if field in marks:
                continue
            label_words = self._nearest_label(field, ocr.words, used)
            if label_words:
                field.label = " ".join(word.text for word in label_words).strip(" :.-")
                field.label_boxes = [word.box for word in label_words]
                field.source_word_ids = [word.id for word in label_words]
                used.update(word.id for word in label_words)
            field.field_type = self._refine_type(field)
        self._infer_colon_gaps(fields, ocr)
        kept = [field for field in fields if self._keep(field, ocr)]
        return self._suppress_overlaps(kept)

    def _keep(self, field: DetectedField, ocr: OCRResult) -> bool:
        inside = [
            word
            for word in ocr.words
            if word.page_index == field.page_index
            and word.box.x >= field.input_box.x
            and word.box.y >= field.input_box.y
            and word.box.x + word.box.width <= field.input_box.x + field.input_box.width
            and word.box.y + word.box.height <= field.input_box.y + field.input_box.height
        ]
        if self._mark_inside_word(field, ocr):
            return False
        if inside and any(term in fold(" ".join(word.text for word in inside)) for term in OFFICE_USE_TERMS):
            return False
        if len(inside) >= 4 and field.field_type not in {FieldType.MULTILINE}:
            return False
        return True

    def _label_marks(self, marks: list[DetectedField], words: list[OCRWord], used: set[str]) -> None:
        """Checkboxes and radios: the text right of each mark is its option, and the marks
        on one row share the question label left of the first mark. OCR often reads the
        mark itself as a glyph ("O", "D"), so words covering a mark are ignored."""
        mark_words = {
            word.id
            for word in words
            for mark in marks
            if word.page_index == mark.page_index and iou(word.box, mark.input_box) >= 0.3
        }
        candidates = [word for word in words if word.id not in mark_words]
        rows: list[list[DetectedField]] = []
        for mark in sorted(marks, key=lambda item: (item.page_index, item.input_box.y, item.input_box.x)):
            mid = mark.input_box.y + mark.input_box.height / 2
            for row in rows:
                first = row[0].input_box
                if row[0].page_index == mark.page_index and abs(first.y + first.height / 2 - mid) <= max(first.height, 0.01):
                    row.append(mark)
                    break
            else:
                rows.append([mark])
        for row in rows:
            row.sort(key=lambda item: item.input_box.x)
            option_words: dict[str, list[OCRWord]] = {}
            for mark in row:
                option_words[mark.id] = self._option_text(mark, candidates)
                used.update(word.id for word in option_words[mark.id])
            question = self._nearest_label(row[0], candidates, used)
            used.update(word.id for word in question)
            question_label = " ".join(word.text for word in question).strip(" :.-")
            for mark in row:
                option = " ".join(word.text for word in option_words[mark.id]).strip(" :.-")
                mark.label = question_label or option
                mark.label_boxes = [word.box for word in question or option_words[mark.id]]
                mark.source_word_ids = [word.id for word in question or option_words[mark.id]]
                if mark.label:
                    mark.options = [FieldOption(id=f"{mark.id}-opt", label=option or mark.label, box=mark.input_box)]

    @staticmethod
    def _option_text(mark: DetectedField, words: list[OCRWord]) -> list[OCRWord]:
        box = mark.input_box
        mid = box.y + box.height / 2
        right_edge = box.x + box.width
        row = sorted(
            (
                word
                for word in words
                if word.page_index == mark.page_index
                and word.box.x >= right_edge - 0.004
                and abs(word.box.y + word.box.height / 2 - mid) <= max(box.height, 0.012)
            ),
            key=lambda item: item.box.x,
        )
        chosen: list[OCRWord] = []
        cursor = right_edge
        for word in row:
            if word.box.x - cursor > (0.03 if not chosen else 0.02):
                break
            chosen.append(word)
            cursor = word.box.x + word.box.width
        return chosen

    def _mark_inside_word(self, field: DetectedField, ocr: OCRResult) -> bool:
        if field.field_type not in {FieldType.CHECKBOX, FieldType.RADIO}:
            return False
        return any(
            word.page_index == field.page_index and self._contains(word.box, field.input_box) for word in ocr.words
        )

    def _nearest_label(self, field: DetectedField, words: list[OCRWord], used: set[str]) -> list[OCRWord]:
        box = field.input_box
        left: list[OCRWord] = []
        above: list[OCRWord] = []
        box_mid_y = box.y + box.height / 2
        for word in words:
            if word.id in used or word.page_index != field.page_index or fold(word.text) in {":", "-", ".", "|"}:
                continue
            word_box = word.box
            word_right = word_box.x + word_box.width
            word_bottom = word_box.y + word_box.height
            word_mid_y = word_box.y + word_box.height / 2
            aligned = abs(word_mid_y - box_mid_y) <= max(box.height * 0.7, 0.018)
            if word_right <= box.x + 0.02 and aligned and box.x - word_right <= 0.28:
                left.append(word)
                continue
            gap = box.y - word_bottom
            overlap = min(word_right, box.x + box.width) - max(word_box.x, box.x)
            if -0.008 <= gap <= 0.035 and overlap >= min(word_box.width, box.width) * 0.2:
                above.append(word)
        if left:
            return self._cluster_left(left)
        return self._cluster_above(above)

    @staticmethod
    def _cluster_left(words: list[OCRWord]) -> list[OCRWord]:
        ordered = sorted(words, key=lambda item: item.box.x)
        chosen = [ordered[-1]]
        for word in reversed(ordered[:-1]):
            gap = chosen[0].box.x - (word.box.x + word.box.width)
            if gap > 0.045:
                break
            chosen.insert(0, word)
        return chosen

    @staticmethod
    def _cluster_above(words: list[OCRWord]) -> list[OCRWord]:
        if not words:
            return []
        nearest = max(words, key=lambda item: item.box.y + item.box.height)
        seed_y = nearest.box.y
        line = [word for word in words if abs(word.box.y - seed_y) <= 0.012]
        line.sort(key=lambda item: item.box.x)
        return line

    def _refine_type(self, field: DetectedField) -> FieldType:
        label = fold(field.label)
        if self._has_term(label, SIGNATURE_TERMS):
            return FieldType.SIGNATURE
        if self._has_term(label, DATE_TERMS):
            return FieldType.DATE
        if any(term in label for term in ADDRESS_TERMS) or field.input_box.height > 0.06:
            if field.field_type not in {FieldType.CHECKBOX, FieldType.RADIO, FieldType.SIGNATURE}:
                return FieldType.MULTILINE
        return field.field_type

    def _infer_colon_gaps(self, fields: list[DetectedField], ocr: OCRResult) -> None:
        existing = [field.input_box for field in fields]
        extra: list[DetectedField] = []
        for word in ocr.words:
            if not word.text.endswith(":"):
                continue
            if any(iou(word.box, box) > 0.2 for box in existing):
                continue
            gap = word.box.model_copy(
                update={
                    "x": min(word.box.x + word.box.width + 0.01, 0.92),
                    "width": min(0.32, 0.96 - (word.box.x + word.box.width)),
                    "label": word.text.rstrip(":"),
                }
            )
            extra.append(
                DetectedField(
                    id=f"p{ocr.page_index}-colon-{word.id}",
                    page_index=ocr.page_index,
                    label=re.sub(r"[:.]+$", "", word.text).strip(),
                    field_type=FieldType.TEXT,
                    input_box=gap,
                    label_boxes=[word.box],
                    source_word_ids=[word.id],
                    confidence=0.55,
                    confidence_reasons=["colon_gap"],
                )
            )
        fields.extend(extra)

    @staticmethod
    def _has_term(label: str, terms: tuple[str, ...]) -> bool:
        for term in terms:
            if len(term) <= 4:
                if re.search(rf"\b{re.escape(term)}\b", label):
                    return True
            elif term in label:
                return True
        return False

    @staticmethod
    def _contains(outer, inner) -> bool:
        return (
            inner.x >= outer.x - 0.004
            and inner.y >= outer.y - 0.004
            and inner.x + inner.width <= outer.x + outer.width + 0.004
            and inner.y + inner.height <= outer.y + outer.height + 0.004
            and inner.width * inner.height <= outer.width * outer.height * 0.85
        )

    def _suppress_overlaps(self, fields: list[DetectedField]) -> list[DetectedField]:
        ranked = sorted(fields, key=lambda item: (item.confidence, 1 if item.label else 0), reverse=True)
        kept: list[DetectedField] = []
        for field in ranked:
            if any(self._same_target(field, other) for other in kept):
                continue
            kept.append(field)
        kept.sort(key=lambda item: (item.page_index, item.input_box.y, item.input_box.x))
        return kept

    @staticmethod
    def _same_target(candidate: DetectedField, kept: DetectedField) -> bool:
        if iou(candidate.input_box, kept.input_box) >= 0.3:
            return True
        left = candidate.input_box
        right = kept.input_box
        overlap_x = min(left.x + left.width, right.x + right.width) - max(left.x, right.x)
        if overlap_x <= 0:
            return False
        shared = overlap_x / max(min(left.width, right.width), 1e-6)
        # Compare against the smaller box: a tall address area must not suppress the
        # separate field stacked just below it.
        overlap_y = min(left.y + left.height, right.y + right.height) - max(left.y, right.y)
        shared_y = overlap_y / max(min(left.height, right.height), 1e-6)
        return shared >= 0.5 and shared_y >= 0.5
