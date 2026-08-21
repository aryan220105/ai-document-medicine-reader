from app.models.ocr import OCRResult, OCRWord
from app.utils.boxes import clamp_box


def make_word(word_id: int, text: str, x: int, y: int, width: int = 80, height: int = 24) -> OCRWord:
    return OCRWord(
        id=word_id,
        text=text,
        confidence=92,
        x=x,
        y=y,
        width=width,
        height=height,
        image_width=1000,
        image_height=1000,
        line_id=y // 40,
    )


def test_ocr_result_structure() -> None:
    words = [make_word(0, "EXP", 610, 720), make_word(1, "DEC", 700, 720), make_word(2, "2027", 790, 720)]
    result = OCRResult(
        full_text="EXP DEC 2027",
        average_confidence=90.0,
        image_width=1000,
        image_height=1000,
        words=words,
        lines=["EXP DEC 2027"],
    )
    assert result.has_useful_text
    box = result.words[0].box
    assert 0.6 < box.x < 0.62
    assert box.width == 0.08
    clamped = clamp_box(box)
    assert 0 <= clamped.x <= 1
    assert 0 <= clamped.width <= 1


def test_bounding_box_normalization() -> None:
    word = make_word(0, "AMOUNT", 100, 200, width=200, height=50)
    assert word.box.x == 0.1
    assert word.box.y == 0.2
    assert word.box.width == 0.2
    assert word.box.height == 0.05
