from __future__ import annotations

from app.models.common import BoundingBox
from app.models.ocr import OCRWord


def union_boxes(boxes: list[BoundingBox], label: str | None = None) -> BoundingBox | None:
    if not boxes:
        return None
    min_x = min(box.x for box in boxes)
    min_y = min(box.y for box in boxes)
    max_x = max(box.x + box.width for box in boxes)
    max_y = max(box.y + box.height for box in boxes)
    return BoundingBox(
        x=min_x,
        y=min_y,
        width=max(max_x - min_x, 0.01),
        height=max(max_y - min_y, 0.01),
        label=label,
    )


def boxes_from_words(words: list[OCRWord], label: str | None = None) -> list[BoundingBox]:
    if not words:
        return []
    grouped: dict[int, list[OCRWord]] = {}
    for word in words:
        grouped.setdefault(word.line_id, []).append(word)
    boxes: list[BoundingBox] = []
    for line_words in grouped.values():
        line_boxes = [word.box for word in line_words]
        merged = union_boxes(line_boxes, label=label)
        if merged:
            boxes.append(merged)
    return boxes


def clamp_box(box: BoundingBox) -> BoundingBox:
    x = min(max(box.x, 0.0), 1.0)
    y = min(max(box.y, 0.0), 1.0)
    return BoundingBox(
        x=x,
        y=y,
        width=min(max(box.width, 0.0), 1.0 - x),
        height=min(max(box.height, 0.0), 1.0 - y),
        label=box.label,
    )
