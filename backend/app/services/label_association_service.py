from __future__ import annotations

import re

from app.models.common import FieldType
from app.models.fields import DetectedField, FieldOption
from app.models.ocr import OCRResult, OCRWord
from app.services.field_semantics_service import FieldSemanticsService
from app.utils.bounding_boxes import iou
from app.utils.text_normalization import dominant_script, fold, is_rtl, language_for_script

SIGNATURE_TERMS = (
    "signature", "applicant signature", "sign here", "thumb impression",
    "हस्ताक्षर", "अंगूठे का निशान", "ಸಹಿ", "ಹೆಬ್ಬೆಟ್ಟಿನ ಗುರುತು", "دستخط", "انگوٹھے کا نشان",
)
DATE_TERMS = (
    "date of birth", "dob", "date", "dated",
    "दिनांक", "तारीख", "जन्म तिथि", "ದಿನಾಂಕ", "ತಾರೀಖು", "ಜನ್ಮ ದಿನಾಂಕ", "تاریخ", "تاریخ پیدائش",
)
ADDRESS_TERMS = (
    "address", "residential address", "permanent address",
    "पता", "स्थायी पता", "ವಿಳಾಸ", "ಶಾಶ್ವತ ವಿಳಾಸ", "پتہ", "مستقل پتہ",
)
OFFICE_USE_TERMS = (
    "office use", "official use", "for office",
    "कार्यालय उपयोग", "ಕಚೇರಿ ಬಳಕೆ", "دفتری استعمال",
)

# How far from a blank, along the row, a printed label may start. Government forms often
# reserve a third of the page width for the label column, so a tight span clips the start
# of a multi-word label -- "Date of Birth" arrives as "Birth" and the dictionary cannot
# match it. The span only decides which words are *candidates*; which of them belong to
# this label is then decided by the word-to-word gaps below, which is what keeps a
# neighbouring column's text out.
LABEL_SEARCH_SPAN = 0.42

# A gap wider than this between two words means the label has ended.
LABEL_WORD_GAP = 0.045


class LabelAssociationService:
    """Attaches each detected blank to the printed label that names it.

    Label search is direction-aware. On a left-to-right page the label sits to the left of
    the blank or on the line above it; on an Urdu page the reading order is mirrored and
    the label sits to the *right*. Searching only leftwards leaves every field on an Urdu
    form unlabelled, which in turn leaves it without guidance.
    """

    def __init__(self, semantics: FieldSemanticsService | None = None) -> None:
        self.semantics = semantics

    def associate(self, fields: list[DetectedField], ocr: OCRResult) -> list[DetectedField]:
        used: set[str] = set()
        rtl = is_rtl(ocr.full_text)
        # Letter glyphs ("O", "D") can pass as checkbox/radio candidates; drop them before
        # labelling so they cannot claim the real labels of neighbouring fields.
        fields = [field for field in fields if not self._mark_inside_word(field, ocr)]
        marks = [field for field in fields if field.field_type in {FieldType.CHECKBOX, FieldType.RADIO}]
        self._label_marks(marks, ocr.words, used, rtl)
        for field in fields:
            if field in marks:
                continue
            label_words = self._nearest_label(field, ocr.words, used, rtl)
            if label_words:
                field.label = " ".join(word.text for word in label_words).strip(" :.-")
                field.label_boxes = [word.box for word in label_words]
                field.source_word_ids = [word.id for word in label_words]
                used.update(word.id for word in label_words)
            field.field_type = self._refine_type(field)
            self._tag_script(field)
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

    def _label_marks(self, marks: list[DetectedField], words: list[OCRWord], used: set[str], rtl: bool = False) -> None:
        """Checkboxes and radios: the text after each mark in reading order is its option,
        and the marks on one row share the question label before the first mark. OCR often
        reads the mark itself as a glyph ("O", "D"), so words covering a mark are ignored.
        On an Urdu page "after" means to the left and "before" means to the right."""
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
            row.sort(key=lambda item: item.input_box.x, reverse=rtl)
            option_words: dict[str, list[OCRWord]] = {}
            for mark in row:
                option_words[mark.id] = self._option_text(mark, candidates, rtl)
                used.update(word.id for word in option_words[mark.id])
            question = self._nearest_label(row[0], candidates, used, rtl)
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
    def _option_text(mark: DetectedField, words: list[OCRWord], rtl: bool = False) -> list[OCRWord]:
        box = mark.input_box
        mid = box.y + box.height / 2
        aligned = [
            word
            for word in words
            if word.page_index == mark.page_index
            and abs(word.box.y + word.box.height / 2 - mid) <= max(box.height, 0.012)
        ]
        if rtl:
            edge = box.x
            row = sorted(
                (word for word in aligned if word.box.x + word.box.width <= edge + 0.004),
                key=lambda item: -item.box.x,
            )
        else:
            edge = box.x + box.width
            row = sorted((word for word in aligned if word.box.x >= edge - 0.004), key=lambda item: item.box.x)
        chosen: list[OCRWord] = []
        cursor = edge
        for word in row:
            gap = (cursor - (word.box.x + word.box.width)) if rtl else (word.box.x - cursor)
            if gap > (0.03 if not chosen else 0.02):
                break
            chosen.append(word)
            cursor = word.box.x if rtl else word.box.x + word.box.width
        return chosen

    def _mark_inside_word(self, field: DetectedField, ocr: OCRResult) -> bool:
        if field.field_type not in {FieldType.CHECKBOX, FieldType.RADIO}:
            return False
        return any(
            word.page_index == field.page_index and self._contains(word.box, field.input_box) for word in ocr.words
        )

    def _nearest_label(
        self, field: DetectedField, words: list[OCRWord], used: set[str], rtl: bool = False
    ) -> list[OCRWord]:
        box = field.input_box
        inline: list[OCRWord] = []
        above: list[OCRWord] = []
        box_mid_y = box.y + box.height / 2
        box_right = box.x + box.width
        for word in words:
            if word.id in used or word.page_index != field.page_index or fold(word.text) in {":", "-", ".", "|"}:
                continue
            word_box = word.box
            word_right = word_box.x + word_box.width
            word_bottom = word_box.y + word_box.height
            word_mid_y = word_box.y + word_box.height / 2
            aligned = abs(word_mid_y - box_mid_y) <= max(box.height * 0.7, 0.018)
            if aligned:
                if rtl:
                    # Label precedes the blank in reading order, i.e. sits to its right.
                    if word_box.x >= box_right - 0.02 and word_box.x - box_right <= LABEL_SEARCH_SPAN:
                        inline.append(word)
                        continue
                elif word_right <= box.x + 0.02 and box.x - word_right <= LABEL_SEARCH_SPAN:
                    inline.append(word)
                    continue
            gap = box.y - word_bottom
            overlap = min(word_right, box_right) - max(word_box.x, box.x)
            if -0.008 <= gap <= 0.035 and overlap >= min(word_box.width, box.width) * 0.2:
                above.append(word)
        if inline:
            return self._cluster_inline(inline, rtl)
        return self._cluster_above(above, rtl)

    @staticmethod
    def _cluster_inline(words: list[OCRWord], rtl: bool = False) -> list[OCRWord]:
        """Walk outward from the blank, taking words until a wide gap says the label has
        ended and a neighbouring field's text has begun.

        The returned list is in *reading* order, not screen order. Tesseract reports Urdu
        words with their real coordinates, so sorting them by ascending x yields the
        visual order, which for a right-to-left script is the reverse of how the words are
        read: "والد کا نام" comes back as "نام کا والد" and matches no alias. Returning
        reading order is what lets one alias list serve every script.
        """
        ordered = sorted(words, key=lambda item: item.box.x)
        if rtl:
            chosen = [ordered[0]]
            for word in ordered[1:]:
                gap = word.box.x - (chosen[-1].box.x + chosen[-1].box.width)
                if gap > LABEL_WORD_GAP:
                    break
                chosen.append(word)
            # Rightmost word first: that is the first word read in Urdu.
            return sorted(chosen, key=lambda item: item.box.x, reverse=True)
        chosen = [ordered[-1]]
        for word in reversed(ordered[:-1]):
            gap = chosen[0].box.x - (word.box.x + word.box.width)
            if gap > LABEL_WORD_GAP:
                break
            chosen.insert(0, word)
        return chosen

    @staticmethod
    def _cluster_above(words: list[OCRWord], rtl: bool = False) -> list[OCRWord]:
        if not words:
            return []
        nearest = max(words, key=lambda item: item.box.y + item.box.height)
        seed_y = nearest.box.y
        line = [word for word in words if abs(word.box.y - seed_y) <= 0.012]
        line.sort(key=lambda item: item.box.x, reverse=rtl)
        return line

    def _refine_type(self, field: DetectedField) -> FieldType:
        """Decide the input type from the printed wording.

        When the dictionary is available it decides, because it covers all four scripts.
        The literal term lists stay as a fallback for callers that construct this service
        without a dictionary.
        """
        if self.semantics is not None:
            match = self.semantics.resolve(field.label, field.field_type)
            if match is not None and match.confident:
                return self.semantics.field_type_for(match.entry.field_type, field.field_type)
        label = fold(field.label)
        if self._has_term(label, SIGNATURE_TERMS):
            return FieldType.SIGNATURE
        if self._has_term(label, DATE_TERMS):
            return FieldType.DATE
        if any(term in label for term in ADDRESS_TERMS) or field.input_box.height > 0.06:
            if field.field_type not in {FieldType.CHECKBOX, FieldType.RADIO, FieldType.SIGNATURE}:
                return FieldType.MULTILINE
        return field.field_type

    def tag_script(self, field: DetectedField) -> None:
        """Public entry point for callers that set a label after association."""
        self._tag_script(field)

    @staticmethod
    def _tag_script(field: DetectedField) -> None:
        """Record which script the label was printed in. Used to choose a default
        explanation language and to pick OCR languages, never to alter the form."""
        if not (field.label or "").strip():
            return
        field.label_script = dominant_script(field.label)
        field.label_language = language_for_script(field.label_script)

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
