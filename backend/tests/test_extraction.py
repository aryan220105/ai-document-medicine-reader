from app.models.ocr import OCRResult, OCRWord
from app.services.extraction_service import ExtractionService


def ocr_from_lines(lines: list[str], confidence: float = 92.0) -> OCRResult:
    words: list[OCRWord] = []
    y = 40
    for line_id, line in enumerate(lines):
        x = 40
        for token in line.split():
            width = max(len(token) * 12, 24)
            words.append(
                OCRWord(
                    id=len(words),
                    text=token,
                    confidence=confidence,
                    x=x,
                    y=y,
                    width=width,
                    height=28,
                    image_width=900,
                    image_height=1200,
                    line_id=line_id,
                )
            )
            x += width + 12
        y += 40
    return OCRResult(
        full_text="\n".join(lines),
        average_confidence=confidence,
        image_width=900,
        image_height=1200,
        words=words,
        lines=lines,
    )


def field_map(fields) -> dict[str, str]:
    return {field.field_type: field.value for field in fields}


def test_date_amount_account_extraction() -> None:
    ocr = ocr_from_lines(
        [
            "ELECTRICITY BILL",
            "Account Number: 12345678",
            "Bill Amount: Rs 2450",
            "Due Date: 25 September 2026",
        ]
    )
    fields = field_map(ExtractionService().extract(ocr))
    assert "12345678" in fields["account_number"]
    assert "2450" in fields["amount"]
    assert "2026" in fields["due_date"]


def test_expiry_and_strength_extraction() -> None:
    ocr = ocr_from_lines(
        [
            "PARACETAMOL TABLETS",
            "500 mg",
            "Batch: ABC123",
            "MFG: JAN 2026",
            "EXP: DEC 2027",
            "Dosage: As directed by physician.",
        ]
    )
    fields = field_map(ExtractionService().extract(ocr))
    assert fields["strength"].lower().replace(" ", "") in {"500mg", "500mg"}
    assert "500" in fields["strength"]
    assert "DEC 2027" in fields["expiry_date"].upper()
    assert "ABC123" in fields["batch_number"]
    assert "physician" in fields["dosage"].lower()
