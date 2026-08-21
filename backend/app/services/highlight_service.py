from __future__ import annotations

from difflib import SequenceMatcher

from app.models.chat import QuestionIntent
from app.models.common import BoundingBox
from app.models.document import DetectedField
from app.models.ocr import OCRResult, OCRWord
from app.utils.boxes import boxes_from_words, clamp_box
from app.utils.text import fold


INTENT_FIELD_MAP = {
    QuestionIntent.FIND_EXPIRY: "expiry_date",
    QuestionIntent.FIND_DOSAGE: "dosage",
    QuestionIntent.FIND_AMOUNT: "amount",
    QuestionIntent.FIND_DUE_DATE: "due_date",
    QuestionIntent.FIND_ACCOUNT_NUMBER: "account_number",
    QuestionIntent.FIND_REFERENCE_NUMBER: "reference_number",
    QuestionIntent.FIND_MEDICINE_NAME: "medicine_name",
    QuestionIntent.FIND_STRENGTH: "strength",
    QuestionIntent.FIND_BATCH: "batch_number",
    QuestionIntent.FIND_MFG: "manufacturing_date",
    QuestionIntent.FIND_WARNING: "warnings",
}


class HighlightService:
    def find_highlights(
        self,
        ocr_result: OCRResult,
        query_intent: QuestionIntent,
        answer_text: str,
        detected_fields: list[DetectedField],
        highlight_phrase: str | None = None,
        force: bool = False,
    ) -> list[BoundingBox]:
        field_type = INTENT_FIELD_MAP.get(query_intent)
        if field_type:
            for field in detected_fields:
                if field.field_type == field_type and field.bounding_boxes:
                    return [clamp_box(box) for box in field.bounding_boxes]

        phrase = highlight_phrase or self._phrase_from_answer(answer_text)
        if phrase:
            matched = self._match_phrase(ocr_result.words, phrase)
            if matched:
                label = field_type.replace("_", " ").title() if field_type else None
                return [clamp_box(box) for box in boxes_from_words(matched, label=label)]

        if force or query_intent == QuestionIntent.VISUAL_LOCATION:
            for field in detected_fields:
                if field.bounding_boxes and fold(field.value) in fold(answer_text):
                    return [clamp_box(box) for box in field.bounding_boxes]
        return []

    def _phrase_from_answer(self, answer_text: str) -> str | None:
        quoted = answer_text.split('"')
        if len(quoted) >= 3:
            return quoted[1].strip()
        return None

    def _match_phrase(self, words: list[OCRWord], phrase: str) -> list[OCRWord]:
        needles = [fold(token) for token in phrase.split() if token.strip()]
        if not needles:
            return []
        folded = [fold(word.text) for word in words]
        best: list[OCRWord] = []
        best_score = 0.0
        for start in range(len(words)):
            window: list[OCRWord] = []
            joined = ""
            for cursor in range(start, min(start + max(len(needles) + 2, 6), len(words))):
                window.append(words[cursor])
                joined = " ".join(fold(item.text) for item in window)
                score = SequenceMatcher(None, joined, " ".join(needles)).ratio()
                if score > best_score and score >= 0.72:
                    best_score = score
                    best = list(window)
                if folded[cursor] == needles[-1] and len(window) >= len(needles):
                    break
        return best
