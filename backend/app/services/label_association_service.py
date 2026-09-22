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


class LabelAssociationService:
    def associate(self, fields: list[DetectedField], ocr: OCRResult) -> list[DetectedField]:
        used: set[str] = set()
        for field in fields:
            label_words = self._nearest_label(field, ocr.words, used)
            if label_words:
                field.label = " ".join(word.text for word in label_words).strip(" :.-")
                field.label_boxes = [word.box for word in label_words]
                field.source_word_ids = [word.id for word in label_words]
                used.update(word.id for word in label_words)
            field.field_type = self._refine_type(field)
            if field.field_type in {FieldType.CHECKBOX, FieldType.RADIO} and field.label:
                field.options = [FieldOption(id=f"{field.id}-opt", label=field.label, box=field.input_box)]
        self._infer_colon_gaps(fields, ocr)
        return [field for field in fields if self._keep(field, ocr)]

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
        if len(inside) >= 4 and field.field_type not in {FieldType.MULTILINE}:
            return False
        return True

    def _nearest_label(self, field: DetectedField, words: list[OCRWord], used: set[str]) -> list[OCRWord]:
        candidates: list[tuple[float, OCRWord]] = []
        box = field.input_box
        for word in words:
            if word.id in used or fold(word.text) in {":", "-", "."}:
                continue
            same_page = word.page_index == field.page_index
            if not same_page:
                continue
            left = word.box.x + word.box.width <= box.x + 0.02
            above = word.box.y + word.box.height <= box.y + 0.015
            if not (left or above):
                continue
            dx = abs((word.box.x + word.box.width) - box.x)
            dy = abs((word.box.y + word.box.height) - box.y)
            if left and abs(word.box.y - box.y) < 0.04:
                score = dx + abs(word.box.y - box.y)
            elif above and abs(word.box.x - box.x) < 0.2:
                score = 0.4 + dy
            else:
                continue
            candidates.append((score, word))
        if not candidates:
            return []
        candidates.sort(key=lambda item: item[0])
        seed = candidates[0][1]
        line = [word for word in words if word.line_id == seed.line_id and word.page_index == seed.page_index]
        line.sort(key=lambda item: item.pixel.x)
        return [word for word in line if word.id not in used][:8]

    def _refine_type(self, field: DetectedField) -> FieldType:
        label = fold(field.label)
        if any(term in label for term in SIGNATURE_TERMS):
            return FieldType.SIGNATURE
        if any(term in label for term in DATE_TERMS):
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
