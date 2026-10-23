"""Complex-script text rendering for the reference preview.

Devanagari, Kannada, and Urdu all need a shaping engine: vowel signs reorder, consonants
form conjuncts, and Arabic letters change form by position and join to their neighbours.
Pillow only shapes text when it was built with libraqm, which is not the case on a plain
``pip install pillow`` on Windows, so a user's Hindi or Urdu answer would be drawn as
disconnected, misordered glyphs -- unusable on a sheet meant to be copied by hand.

This module shapes with HarfBuzz and rasterises with FreeType when both are installed,
and reports honestly when it cannot, so the caller can warn instead of printing nonsense.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from app.utils.text_normalization import dominant_script

logger = logging.getLogger(__name__)

try:  # pragma: no cover - import guard
    import freetype
    import uharfbuzz as hb

    SHAPING_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    freetype = None
    hb = None
    SHAPING_AVAILABLE = False


# HarfBuzz script tags and base direction per script.
SCRIPT_TAGS = {
    "devanagari": ("Deva", "ltr"),
    "kannada": ("Knda", "ltr"),
    "arabic": ("Arab", "rtl"),
    "latin": ("Latn", "ltr"),
    "unknown": ("Latn", "ltr"),
}

# Fonts that actually carry each script, most preferred first. Nirmala UI covers the
# Indic scripts on Windows; Tahoma carries a usable Naskh for Urdu. The Noto and DejaVu
# paths cover Linux containers.
FONT_CANDIDATES: dict[str, tuple[str, ...]] = {
    "devanagari": (
        "C:/Windows/Fonts/Nirmala.ttc",
        "C:/Windows/Fonts/mangal.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
    ),
    "kannada": (
        "C:/Windows/Fonts/Nirmala.ttc",
        "C:/Windows/Fonts/tunga.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Regular.ttf",
        "/usr/share/fonts/truetype/lohit-kannada/Lohit-Kannada.ttf",
    ),
    "arabic": (
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ),
    "latin": (
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ),
}
FONT_CANDIDATES["unknown"] = FONT_CANDIDATES["latin"]


@dataclass
class ShapedText:
    image: Image.Image
    width: int
    height: int
    baseline: int


def font_for(script: str) -> str | None:
    for path in FONT_CANDIDATES.get(script, FONT_CANDIDATES["latin"]):
        if Path(path).exists():
            return path
    for path in FONT_CANDIDATES["latin"]:
        if Path(path).exists():
            return path
    return None


def can_shape(text: str) -> bool:
    """Whether this text can be rendered faithfully.

    Latin needs no shaping, so it is always fine. Anything else needs HarfBuzz and a font
    that covers the script.
    """
    script = dominant_script(text)
    if script in {"latin", "unknown"}:
        return True
    return SHAPING_AVAILABLE and font_for(script) is not None


@lru_cache(maxsize=16)
def _faces(font_path: str, face_index: int = 0):
    with open(font_path, "rb") as handle:
        data = handle.read()
    face = hb.Face(data, face_index)
    return face


def measure(text: str, size: int, script: str | None = None) -> int:
    """Advance width in pixels of `text` at `size`, after shaping."""
    layout = _shape(text, size, script)
    if layout is None:
        return len(text) * size // 2
    return layout[0]


def _shape(text: str, size: int, script: str | None = None):
    """Returns (advance_width, glyphs, font_path, face_index) or None."""
    if not SHAPING_AVAILABLE or not text:
        return None
    script = script or dominant_script(text)
    tag, direction = SCRIPT_TAGS.get(script, SCRIPT_TAGS["latin"])
    font_path = font_for(script)
    if font_path is None:
        return None
    face_index = 0
    try:
        face = _faces(font_path, face_index)
        hb_font = hb.Font(face)
        hb_font.scale = (size * 64, size * 64)
        hb.ot_font_set_funcs(hb_font)
        buffer = hb.Buffer()
        buffer.add_str(text)
        buffer.direction = direction
        buffer.script = tag
        hb.shape(hb_font, buffer, None)
    except Exception:
        logger.debug("Shaping failed for script=%s", script)
        return None
    pen = 0.0
    glyphs: list[tuple[int, float, float]] = []
    for info, position in zip(buffer.glyph_infos, buffer.glyph_positions):
        glyphs.append((info.codepoint, pen + position.x_offset / 64.0, position.y_offset / 64.0))
        pen += position.x_advance / 64.0
    return int(round(pen)), glyphs, font_path, face_index


def render_line(text: str, size: int, colour: tuple[int, int, int] = (20, 40, 70)) -> ShapedText | None:
    """Rasterise one shaped line onto a transparent image, ready to paste."""
    layout = _shape(text, size)
    if layout is None:
        return None
    advance, glyphs, font_path, face_index = layout
    if advance <= 0:
        return None
    # Generous padding. Naskh final forms (ـم, ـج) drop well below the baseline and
    # Devanagari/Kannada stack vowel signs high above it, so a tight box silently loses
    # the last letter of a word.
    ascent = int(size * 1.6)
    descent = int(size * 1.0)
    width = advance + 2 * size
    height = ascent + descent
    alpha = np.zeros((height, width), np.uint8)
    try:
        ft_face = freetype.Face(font_path, face_index)
        ft_face.set_char_size(size * 64)
    except Exception:
        return None
    for glyph_id, dx, dy in glyphs:
        try:
            ft_face.load_glyph(glyph_id, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
        except Exception:
            continue
        bitmap = ft_face.glyph.bitmap
        if bitmap.width == 0 or bitmap.rows == 0:
            continue
        buffer = np.array(bitmap.buffer, np.uint8)
        if buffer.size < bitmap.rows * bitmap.pitch:
            continue
        glyph = buffer.reshape(bitmap.rows, bitmap.pitch)[:, : bitmap.width]
        x0 = int(round(dx)) + ft_face.glyph.bitmap_left + size // 2
        y0 = ascent - int(round(dy)) - ft_face.glyph.bitmap_top
        # Clip the glyph to the canvas rather than dropping it: a letter that overhangs
        # by a pixel should lose that pixel, not disappear from the word.
        src_x = max(0, -x0)
        src_y = max(0, -y0)
        dst_x = max(0, x0)
        dst_y = max(0, y0)
        copy_w = min(bitmap.width - src_x, width - dst_x)
        copy_h = min(bitmap.rows - src_y, height - dst_y)
        if copy_w <= 0 or copy_h <= 0:
            continue
        patch = glyph[src_y : src_y + copy_h, src_x : src_x + copy_w]
        region = alpha[dst_y : dst_y + copy_h, dst_x : dst_x + copy_w]
        alpha[dst_y : dst_y + copy_h, dst_x : dst_x + copy_w] = np.maximum(region, patch)
    if not alpha.any():
        return None
    rgba = np.zeros((height, width, 4), np.uint8)
    rgba[:, :, 0], rgba[:, :, 1], rgba[:, :, 2] = colour
    rgba[:, :, 3] = alpha
    return ShapedText(image=Image.fromarray(rgba, "RGBA"), width=width, height=height, baseline=ascent)
