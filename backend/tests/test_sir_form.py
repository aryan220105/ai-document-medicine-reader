from app.models.common import FieldType, NormalizedBoundingBox
from app.models.fields import DetectedField
from app.models.ocr import OCRResult
from app.services.sir_form_service import SirFormService


def _field(label: str, y: float, x: float, width: float, height: float = 0.016, page: int = 0) -> DetectedField:
    return DetectedField(
        id=f"{page}-{y}-{x}",
        page_index=page,
        label=label,
        field_type=FieldType.TEXT,
        input_box=NormalizedBoundingBox(x=x, y=y, width=width, height=height, page_index=page),
        confidence=0.8,
    )


def _page(text: str) -> OCRResult:
    return OCRResult(full_text=text, image_width=1000, image_height=1400)


def test_hindi_sir_repairs_the_part_number_and_adds_the_missing_relationship():
    fields = [
        _field("भाग संख्या हि", 0.403, 0.217, 0.138, 0.031),
        _field("संबंध:", 0.298, 0.539, 0.387),
    ]
    ocr = [_page("आवेदक का नाम मतदाता का विवरण विधानसभा")]
    corrected = SirFormService().correct(fields, ocr)
    labels = [field.label for field in corrected]
    assert "भाग संख्या" in labels
    assert "भाग संख्या हि" not in labels
    assert labels.count("संबंध") == 2


def test_kannada_sir_repairs_the_address():
    fields = [_field("ಎಳಾಸ", 0.163, 0.111, 0.819)]
    ocr = [_page("ಅರ್ಜಿದಾರರ ಹೆಸರು ಮತದಾರರ ವಿವರ")]
    corrected = SirFormService().correct(fields, ocr)
    assert corrected[0].label == "ವಿಳಾಸ"


def test_urdu_sir_names_both_relationship_columns():
    fields = [_field("رشتہ:رشتہ", 0.360, 0.074, 0.423, 0.021)]
    ocr = [_page("درخواست دہندہ ووٹر کا نام")]
    corrected = SirFormService().correct(fields, ocr)
    labels = [field.label for field in corrected]
    assert labels.count("رشتہ") == 2
    assert "رشتہ:رشتہ" not in labels


def test_another_form_is_left_unchanged():
    fields = [_field("Account Number", 0.4, 0.2, 0.4)]
    ocr = [_page("Demo Bank Account Opening Form nominee occupation")]
    corrected = SirFormService().correct(fields, ocr)
    assert corrected == fields
    assert len(corrected) == 1
