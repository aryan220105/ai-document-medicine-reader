from __future__ import annotations

from app.models.common import NormalizedBoundingBox, PixelBoundingBox


def normalize_box(pixel: PixelBoundingBox, label: str | None = None) -> NormalizedBoundingBox:
    iw = max(pixel.image_width, 1)
    ih = max(pixel.image_height, 1)
    return clamp_box(
        NormalizedBoundingBox(
            x=pixel.x / iw,
            y=pixel.y / ih,
            width=pixel.width / iw,
            height=pixel.height / ih,
            page_index=pixel.page_index,
            label=label,
        )
    )


def clamp_box(box: NormalizedBoundingBox) -> NormalizedBoundingBox:
    x = min(max(box.x, 0.0), 1.0)
    y = min(max(box.y, 0.0), 1.0)
    return NormalizedBoundingBox(
        x=x,
        y=y,
        width=min(max(box.width, 0.0), 1.0 - x),
        height=min(max(box.height, 0.0), 1.0 - y),
        page_index=box.page_index,
        label=box.label,
    )


def iou(a: NormalizedBoundingBox, b: NormalizedBoundingBox) -> float:
    if a.page_index != b.page_index:
        return 0.0
    ax2, ay2 = a.x + a.width, a.y + a.height
    bx2, by2 = b.x + b.width, b.y + b.height
    ix1, iy1 = max(a.x, b.x), max(a.y, b.y)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = a.width * a.height + b.width * b.height - inter
    return inter / union if union else 0.0


def union_boxes(boxes: list[NormalizedBoundingBox], label: str | None = None) -> NormalizedBoundingBox | None:
    if not boxes:
        return None
    min_x = min(box.x for box in boxes)
    min_y = min(box.y for box in boxes)
    max_x = max(box.x + box.width for box in boxes)
    max_y = max(box.y + box.height for box in boxes)
    return clamp_box(
        NormalizedBoundingBox(
            x=min_x,
            y=min_y,
            width=max(max_x - min_x, 0.01),
            height=max(max_y - min_y, 0.01),
            page_index=boxes[0].page_index,
            label=label,
        )
    )
