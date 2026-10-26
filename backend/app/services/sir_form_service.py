"""Canonical labels for the Special Intensive Revision declaration form.

The four official PDFs (English, Hindi, Kannada, Urdu) print the same blanks.
OCR misreads a few of them and sometimes merges the two comparison columns into
one caption. Once the page text shows this is that form, each blank is named
from the position it occupies. Any other form is returned untouched.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.common import FieldType, NormalizedBoundingBox
from app.models.fields import DetectedField
from app.models.ocr import OCRResult
from app.utils.text_normalization import dominant_script, fold

_Y = 0.016


@dataclass(frozen=True)
class _Slot:
    page: int
    y: float
    x: float
    width: float
    height: float
    field_type: str
    label: str
    insert: bool = False


def _slots() -> dict[str, tuple[_Slot, ...]]:
    text = "text"
    sign = "signature"
    hi = (
        _Slot(0, 0.263, 0.352, 0.145, 0.014, text, "मतदाता का ईपीआईसी नंबर (यदि उपलब्ध हो)"),
        _Slot(0, 0.263, 0.780, 0.146, 0.014, text, "मतदाता का ईपीआईसी नंबर (यदि उपलब्ध हो)"),
        _Slot(0, 0.280, 0.157, 0.340, 0.014, text, "संबंधी का नाम"),
        _Slot(0, 0.280, 0.585, 0.341, 0.014, text, "संबंधी का नाम"),
        _Slot(0, 0.298, 0.539, 0.387, 0.014, text, "संबंध"),
        _Slot(0, 0.298, 0.110, 0.385, 0.014, text, "संबंध", insert=True),
        _Slot(0, 0.315, 0.112, 0.385, 0.014, text, "जिला"),
        _Slot(0, 0.315, 0.541, 0.385, 0.014, text, "जिला"),
        _Slot(0, 0.403, 0.074, 0.138, 0.031, text, "विधानसभा निर्वाचन क्षेत्र संख्या"),
        _Slot(0, 0.403, 0.217, 0.138, 0.031, text, "भाग संख्या"),
        _Slot(0, 0.403, 0.359, 0.138, 0.031, text, "क्रम संख्या"),
        _Slot(0, 0.403, 0.502, 0.138, 0.031, text, "विधानसभा निर्वाचन क्षेत्र संख्या"),
        _Slot(0, 0.403, 0.645, 0.138, 0.031, text, "भाग संख्या"),
        _Slot(0, 0.403, 0.788, 0.139, 0.031, text, "क्रम संख्या"),
        _Slot(0, 0.471, 0.502, 0.424, 0.016, text, "पिता/अभिभावक का ईपीआईसी नंबर (यदि उपलब्ध हो)"),
        _Slot(0, 0.490, 0.502, 0.424, 0.016, text, "माता का नाम"),
        _Slot(0, 0.510, 0.502, 0.424, 0.016, text, "माता का ईपीआईसी नंबर (यदि उपलब्ध हो)"),
        _Slot(0, 0.549, 0.502, 0.424, 0.016, text, "जीवनसाथी का ईपीआईसी नंबर (यदि उपलब्ध हो)"),
        _Slot(0, 0.845, 0.550, 0.380, 0.016, text, "बीएलओ का नाम और दूरभाष संख्या", insert=True),
    )
    epic_kn = "ಮತದಾರರ ಭಾವಚಿತ್ರ ಗುರುತಿನ ಚೀಟಿ ಸಂಖ್ಯೆ (ಲಭ್ಯವಿದ್ದರೆ)"
    kn = (
        _Slot(0, 0.163, 0.111, 0.819, 0.014, text, "ವಿಳಾಸ"),
        _Slot(0, 0.350, 0.090, 0.408, 0.027, text, "ಜಿಲ್ಲೆ"),
        _Slot(0, 0.350, 0.529, 0.408, 0.027, text, "ಜಿಲ್ಲೆ"),
        _Slot(0, 0.530, 0.502, 0.435, 0.020, text, f"ತಂದೆಯ/ಪೋಷಕರ {epic_kn}"),
        _Slot(0, 0.578, 0.502, 0.435, 0.020, text, f"ತಾಯಿಯ {epic_kn}"),
        _Slot(0, 0.626, 0.502, 0.435, 0.023, text, f"ಸಂಗಾತಿಯ {epic_kn}"),
        _Slot(0, 0.952, 0.500, 0.420, 0.020, text, "ಬಿಎಲ್‌ಒ ರವರ ಹೆಸರು ಮತ್ತು ದೂರವಾಣಿ ಸಂಖ್ಯೆ", insert=True),
    )
    voter = "ووٹر کا نام"
    epic_ur = "ووٹر کا ای پی آئی سی نمبر (اگر دستیاب ہو)"
    relative = "رشتہ دار کا نام"
    ac = "اسمبلی انتخابی حلقے کا نام"
    ur = (
        _Slot(0, 0.284, 0.074, 0.320, 0.022, text, voter),
        _Slot(0, 0.284, 0.500, 0.220, 0.022, text, voter, insert=True),
        _Slot(0, 0.310, 0.074, 0.220, 0.021, text, epic_ur),
        _Slot(0, 0.310, 0.500, 0.220, 0.021, text, epic_ur, insert=True),
        _Slot(0, 0.335, 0.074, 0.300, 0.022, text, relative),
        _Slot(0, 0.335, 0.500, 0.220, 0.022, text, relative, insert=True),
        _Slot(0, 0.360, 0.074, 0.200, 0.021, text, "رشتہ"),
        _Slot(0, 0.360, 0.500, 0.200, 0.021, text, "رشتہ", insert=True),
        _Slot(0, 0.385, 0.074, 0.200, 0.022, text, "ضلع"),
        _Slot(0, 0.385, 0.500, 0.200, 0.022, text, "ضلع", insert=True),
        _Slot(0, 0.411, 0.074, 0.200, 0.021, text, "ریاست"),
        _Slot(0, 0.411, 0.500, 0.200, 0.021, text, "ریاست", insert=True),
        _Slot(0, 0.436, 0.074, 0.251, 0.022, text, ac),
        _Slot(0, 0.436, 0.500, 0.220, 0.022, text, ac, insert=True),
        _Slot(1, 0.130, 0.620, 0.300, 0.020, text, "بی ایل او کا نام اور ٹیلی فون نمبر", insert=True),
    )
    return {"hi": hi, "kn": kn, "ur": ur}


class SirFormService:
    def __init__(self) -> None:
        self._slots = _slots()

    def correct(self, fields: list[DetectedField], ocr_pages: list[OCRResult]) -> list[DetectedField]:
        language = self._language(ocr_pages)
        if language is None:
            return fields
        slots = self._slots.get(language)
        if not slots:
            return fields
        remaining = list(fields)
        claimed: set[int] = set()
        corrected: list[DetectedField] = list(fields)
        for index, slot in enumerate(slots):
            match = self._nearest(remaining, slot, claimed)
            if match is None:
                if slot.insert:
                    corrected.append(self._new_field(slot, index))
                continue
            claimed.add(id(match))
            self._rename(match, slot)
        corrected.sort(key=lambda field: (field.page_index, field.input_box.y, field.input_box.x))
        return corrected

    @staticmethod
    def _language(ocr_pages: list[OCRResult]) -> str | None:
        text = "\n".join(page.full_text for page in ocr_pages)
        if not text.strip():
            return None
        folded = fold(text)
        script = dominant_script(text)
        if script == "devanagari" and "आवेदक" in text and "मतदाता" in text:
            return "hi"
        if script == "kannada" and "ಮತದಾರ" in text and "ಅರ್ಜಿ" in text:
            return "kn"
        if script == "arabic" and "ووٹر" in text and ("درخواست" in text or "اعلامیہ" in text):
            return "ur"
        if script == "latin" and "epic" in folded and "applicant" in folded and "electoral" in folded:
            return "en"
        return None

    @staticmethod
    def _nearest(fields: list[DetectedField], slot: _Slot, claimed: set[int]) -> DetectedField | None:
        best: DetectedField | None = None
        best_distance = 1.0
        slot_right = slot.x + slot.width
        slot_center = slot.x + slot.width / 2
        for field in fields:
            if id(field) in claimed or field.page_index != slot.page:
                continue
            if abs(field.input_box.y - slot.y) > _Y:
                continue
            field_right = field.input_box.x + field.input_box.width
            overlap = min(field_right, slot_right) - max(field.input_box.x, slot.x)
            if overlap <= 0:
                continue
            center = field.input_box.x + field.input_box.width / 2
            distance = abs(center - slot_center)
            if distance < best_distance:
                best = field
                best_distance = distance
        return best

    @staticmethod
    def _rename(field: DetectedField, slot: _Slot) -> None:
        previous = field.label
        field.label = slot.label
        field.caption = slot.label
        if not field.display_label or field.display_label == previous:
            field.display_label = slot.label
        if "sir_layout" not in field.confidence_reasons:
            field.confidence_reasons = [*field.confidence_reasons, "sir_layout"]
        field.confidence = max(field.confidence, 0.9)

    @staticmethod
    def _new_field(slot: _Slot, index: int) -> DetectedField:
        return DetectedField(
            id=f"sir-p{slot.page}-{index}",
            page_index=slot.page,
            label=slot.label,
            caption=slot.label,
            display_label=slot.label,
            field_type=FieldType(slot.field_type),
            input_box=NormalizedBoundingBox(
                x=slot.x,
                y=slot.y,
                width=slot.width,
                height=slot.height,
                page_index=slot.page,
            ),
            confidence=0.93,
            confidence_reasons=["sir_layout"],
            structure_origin="sir_layout",
        )
