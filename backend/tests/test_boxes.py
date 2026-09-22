from app.models.common import PixelBoundingBox
from app.utils.bounding_boxes import clamp_box, iou, normalize_box
from app.models.common import NormalizedBoundingBox


def test_normalize_and_clamp():
    box = normalize_box(PixelBoundingBox(x=50, y=100, width=100, height=50, image_width=200, image_height=200))
    assert box.x == 0.25
    assert box.y == 0.5
    assert box.width == 0.5
    assert box.height == 0.25
    overflow = clamp_box(NormalizedBoundingBox(x=0.9, y=0.9, width=0.5, height=0.5, page_index=0))
    assert overflow.x + overflow.width <= 1.0001


def test_iou_merge():
    a = NormalizedBoundingBox(x=0.1, y=0.1, width=0.2, height=0.2, page_index=0)
    b = NormalizedBoundingBox(x=0.12, y=0.12, width=0.2, height=0.2, page_index=0)
    assert iou(a, b) > 0.4
