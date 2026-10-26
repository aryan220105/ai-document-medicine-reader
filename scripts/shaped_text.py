"""Shaped text drawing for the sample generator.

Reuses the backend's HarfBuzz shaper so the synthetic Hindi, Kannada, and Urdu forms
carry correctly shaped text. Without shaping the samples would be unreadable to Tesseract
and the evaluation numbers taken from them would be meaningless.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.utils import text_shaping  # noqa: E402
from app.utils.text_normalization import dominant_script  # noqa: E402

SHAPING_AVAILABLE = text_shaping.SHAPING_AVAILABLE


def latin_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def text_width(text: str, size: int) -> int:
    script = dominant_script(text)
    if script in {"latin", "unknown"}:
        return int(latin_font(size).getlength(text))
    return text_shaping.measure(text, size, script)


def draw_text(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    size: int,
    fill: tuple[int, int, int] = (30, 45, 70),
    anchor_right: bool = False,
) -> int:
    """Draw `text` at `position` (top-left, or top-right when `anchor_right`).

    Returns the drawn width. Latin text goes through Pillow; anything else is shaped.
    """
    script = dominant_script(text)
    if script in {"latin", "unknown"}:
        font = latin_font(size)
        width = int(font.getlength(text))
        x = position[0] - width if anchor_right else position[0]
        draw.text((x, position[1]), text, fill=fill, font=font)
        return width

    rendered = text_shaping.render_line(text, size, colour=fill)
    if rendered is None:
        raise RuntimeError(f"Could not shape {script} text: {text!r}")
    # `render_line` leaves a half-em of side bearing; trim it so the caller's coordinates
    # line up with where the ink actually starts.
    bbox = rendered.image.getbbox()
    cropped = rendered.image.crop(bbox) if bbox else rendered.image
    width = cropped.width
    x = position[0] - width if anchor_right else position[0]
    image.paste(cropped, (int(x), int(position[1])), cropped)
    return width
