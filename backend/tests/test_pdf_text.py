"""The Hindi enumeration form stores its labels in the PDF. OCR of that page
reorders vowel signs, so a real text layer has to win."""

from __future__ import annotations

from pathlib import Path

import fitz

from app.services.pdf_service import PdfService


def test_a_digital_page_is_read_from_its_own_text(tmp_path: Path):
    source = tmp_path / "form.pdf"
    document = fitz.open()
    page = document.new_page(width=600, height=800)
    lines = [
        "Elector name",
        "EPIC number",
        "Date of birth",
        "Relative name",
        "Relationship",
        "District",
        "State name",
        "Assembly constituency",
        "Part number",
        "Serial number",
        "Mobile number",
        "Aadhaar number",
    ]
    for index, line in enumerate(lines):
        page.insert_text((72, 80 + index * 28), line + " :", fontsize=12)
    document.save(source)
    document.close()

    result = PdfService().read_embedded_text(source, 0, 1200, 1600)
    assert result is not None
    text = result.full_text
    assert "Elector name" in text
    assert "Relationship" in text
    assert any(word.text == ":" for word in result.words)
    assert result.words[0].pixel.image_width == 1200
    assert result.words[0].pixel.x > 0


def test_urdu_presentation_forms_fold_to_letters():
    from app.services.pdf_service import pdf_word_text

    # Isolated presentation forms, as the digital Urdu SIR export stores them.
    shaped = "\ufe8d\ufecb\ufefc\ufee3\ufbff\ufba7"
    assert pdf_word_text(shaped) == "اعلامیہ"
    assert "\ufe8d" not in pdf_word_text(shaped)


def test_a_misencoded_devanagari_layer_is_left_to_ocr():
    from app.models.common import PixelBoundingBox
    from app.models.ocr import OCRWord

    def word(text: str, index: int) -> OCRWord:
        return OCRWord(
            id=str(index),
            text=text,
            confidence=99,
            page_index=0,
            pixel=PixelBoundingBox(x=10, y=10 + index, width=40, height=12, image_width=100, image_height=100, page_index=0),
        )

    broken = [word("पि3छले", i) for i in range(8)]
    assert PdfService._devanagari_layer_is_misencoded(broken) is True
    urdu_with_a_form_number = [word("فارم6", i) for i in range(12)]
    assert PdfService._devanagari_layer_is_misencoded(urdu_with_a_form_number) is False


def test_embedded_urdu_keeps_pdf_reading_order():
    from app.services.page_structure_service import reading_text
    from app.models.common import PixelBoundingBox
    from app.models.ocr import OCRWord

    def word(text: str, index: int, x: int) -> OCRWord:
        return OCRWord(
            id=str(index),
            text=text,
            confidence=99,
            page_index=0,
            pixel=PixelBoundingBox(x=x, y=40, width=30, height=14, image_width=800, image_height=1000, page_index=0),
            reading_index=index,
        )

    # x is deliberately scrambled. The PDF's own order is the reading order.
    words = [
        word(":درخواست", 0, 463),
        word("دہندہ", 1, 488),
        word("کا", 2, 478),
        word("نام", 3, 466),
    ]
    assert reading_text(words) == ":درخواست دہندہ کا نام"


def test_a_scan_without_text_stays_with_ocr(tmp_path: Path):
    source = tmp_path / "scan.pdf"
    document = fitz.open()
    document.new_page(width=600, height=800)
    document.save(source)
    document.close()
    assert PdfService().read_embedded_text(source, 0, 1200, 1600) is None
