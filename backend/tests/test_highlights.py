from app.models.chat import QuestionIntent
from app.services.extraction_service import ExtractionService
from app.services.highlight_service import HighlightService
from tests.test_extraction import ocr_from_lines


def test_highlight_matching_uses_field_boxes() -> None:
    ocr = ocr_from_lines(
        ["PARACETAMOL TABLETS", "500 mg", "EXP: DEC 2027"],
    )
    fields = ExtractionService().extract(ocr)
    highlights = HighlightService().find_highlights(
        ocr,
        QuestionIntent.FIND_EXPIRY,
        "The expiry date shown is DEC 2027.",
        fields,
        force=True,
    )
    assert highlights
    box = highlights[0]
    assert 0 <= box.x <= 1
    assert 0 <= box.y <= 1
    assert box.width > 0
    assert box.height > 0
