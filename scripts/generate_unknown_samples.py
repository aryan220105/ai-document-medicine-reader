"""Generate synthetic *unknown* forms in English, Hindi, Kannada, and Urdu.

These are deliberately not in the known-form knowledge base, so they exercise the
unknown-form path end to end: OCR in the right script, label association (right-to-left
for Urdu), dictionary resolution, and guidance in every language.

Each form is written twice: a clean scan and a noisy one (rotation, blur, lower contrast,
speckle) so robustness can be measured rather than assumed.

    python scripts/generate_unknown_samples.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from shaped_text import draw_text, latin_font, text_width  # noqa: E402

SAMPLES = ROOT / "samples"
GT = SAMPLES / "ground_truth"

WIDTH, HEIGHT = 1240, 1500
INK = (24, 36, 56)
RULE = (70, 86, 110)

# Each form: a title, a note, and rows of (semantic field id, printed label, type).
# The labels are ordinary wordings a real regional form would print, and the semantic ids
# are what the dictionary is expected to resolve them to.
FORMS = {
    "en": {
        "name": "demo_unknown_en_library",
        "title": "Demo Community Library Membership Request",
        "note": "SYNTHETIC DEMO FORM - not an official document",
        "rtl": False,
        "rows": [
            ("full_name", "Full Name", "text"),
            ("father_name", "Father's Name", "text"),
            ("date_of_birth", "Date of Birth", "date"),
            ("mobile_number", "Mobile Number", "text"),
            ("email", "Email ID", "text"),
            ("pincode", "PIN Code", "text"),
            ("address", "Residential Address", "multiline"),
            ("declaration_date", "Date", "date"),
            ("signature", "Signature of Applicant", "signature"),
        ],
        "unknowable": ("Favourite Genre", "Shelf Preference"),
    },
    "hi": {
        "name": "demo_unknown_hi_panchayat",
        "title": "डेमो ग्राम पंचायत सेवा आवेदन",
        "note": "कृत्रिम डेमो फ़ॉर्म - आधिकारिक दस्तावेज़ नहीं",
        "rtl": False,
        "rows": [
            ("full_name", "पूरा नाम", "text"),
            ("father_name", "पिता का नाम", "text"),
            ("date_of_birth", "जन्म तिथि", "date"),
            ("mobile_number", "मोबाइल नंबर", "text"),
            ("aadhaar_number", "आधार संख्या", "text"),
            ("pincode", "पिन कोड", "text"),
            ("permanent_address", "स्थायी पता", "multiline"),
            ("annual_income", "वार्षिक आय", "text"),
            ("signature", "हस्ताक्षर", "signature"),
        ],
        "unknowable": ("पसंदीदा विषय",),
    },
    "kn": {
        "name": "demo_unknown_kn_grama",
        "title": "ಡೆಮೊ ಗ್ರಾಮ ಸೇವಾ ಅರ್ಜಿ ನಮೂನೆ",
        "note": "ಕೃತಕ ಡೆಮೊ ಅರ್ಜಿ - ಅಧಿಕೃತ ದಾಖಲೆ ಅಲ್ಲ",
        "rtl": False,
        "rows": [
            ("full_name", "ಪೂರ್ಣ ಹೆಸರು", "text"),
            ("father_name", "ತಂದೆಯ ಹೆಸರು", "text"),
            ("date_of_birth", "ಜನ್ಮ ದಿನಾಂಕ", "date"),
            ("mobile_number", "ಮೊಬೈಲ್ ಸಂಖ್ಯೆ", "text"),
            ("bank_account_number", "ಬ್ಯಾಂಕ್ ಖಾತೆ ಸಂಖ್ಯೆ", "text"),
            ("pincode", "ಪಿನ್ ಕೋಡ್", "text"),
            ("address", "ವಿಳಾಸ", "multiline"),
            ("occupation", "ವೃತ್ತಿ", "text"),
            ("signature", "ಸಹಿ", "signature"),
        ],
        "unknowable": ("ಇಷ್ಟದ ವಿಷಯ",),
    },
    "ur": {
        "name": "demo_unknown_ur_welfare",
        "title": "ڈیمو فلاحی امداد درخواست فارم",
        "note": "مصنوعی ڈیمو فارم - سرکاری دستاویز نہیں",
        "rtl": True,
        "rows": [
            ("full_name", "پورا نام", "text"),
            ("father_name", "والد کا نام", "text"),
            ("date_of_birth", "تاریخ پیدائش", "date"),
            ("mobile_number", "موبائل نمبر", "text"),
            ("aadhaar_number", "آدھار نمبر", "text"),
            ("pincode", "پن کوڈ", "text"),
            ("permanent_address", "مستقل پتہ", "multiline"),
            ("annual_income", "سالانہ آمدنی", "text"),
            ("signature", "دستخط", "signature"),
        ],
        "unknowable": ("پسندیدہ موضوع",),
    },
}


def field_gt(field_id: str, label: str, ftype: str, pixel: tuple[int, int, int, int]) -> dict:
    x, y, w, h = pixel
    return {
        "field_id": field_id,
        "label": label,
        "type": ftype,
        "pixel": {"x": x, "y": y, "width": w, "height": h, "image_width": WIDTH, "image_height": HEIGHT},
        "options": [],
    }


def draw_box(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    draw.rectangle((x, y, x + w, y + h), outline=RULE, width=2)
    return (x, y, w, h)


def draw_underline(draw: ImageDraw.ImageDraw, x: int, y: int, w: int) -> tuple[int, int, int, int]:
    draw.line((x, y + 34, x + w, y + 34), fill=RULE, width=2)
    return (x, y, w, 38)


def build(spec: dict) -> tuple[Image.Image, list[dict]]:
    image = Image.new("RGB", (WIDTH, HEIGHT), (250, 250, 248))
    draw = ImageDraw.Draw(image)
    rtl = spec["rtl"]
    margin = 64
    label_size, body_size = 24, 22

    # Header. Right-aligned for Urdu, matching how such a form is actually printed.
    title_x = WIDTH - margin if rtl else margin
    draw_text(image, draw, (title_x, 44), spec["title"], 32, INK, anchor_right=rtl)
    draw_text(image, draw, (title_x, 96), spec["note"], 18, (150, 70, 50), anchor_right=rtl)
    draw.line((margin, 134, WIDTH - margin, 134), fill=RULE, width=1)

    fields: list[dict] = []
    y = 190
    label_column = 420  # width reserved for the printed label
    for field_id, label, ftype in spec["rows"]:
        if ftype == "multiline":
            lx = WIDTH - margin if rtl else margin
            draw_text(image, draw, (lx, y), label, label_size, INK, anchor_right=rtl)
            pixel = draw_box(draw, margin, y + 40, WIDTH - 2 * margin, 110)
            fields.append(field_gt(field_id, label, ftype, pixel))
            y += 190
            continue

        if rtl:
            # Label on the right, blank to its left.
            draw_text(image, draw, (WIDTH - margin, y), label, label_size, INK, anchor_right=True)
            box_right = WIDTH - margin - label_column
            box_width = box_right - margin
            if ftype == "date":
                pixel = draw_underline(draw, margin + 120, y - 4, box_width - 120)
            elif ftype == "signature":
                pixel = draw_box(draw, box_right - 420, y - 6, 420, 86)
            else:
                pixel = draw_box(draw, margin, y - 6, box_width, 44)
        else:
            draw_text(image, draw, (margin, y), label, label_size, INK)
            box_left = margin + label_column
            box_width = WIDTH - margin - box_left
            if ftype == "date":
                pixel = draw_underline(draw, box_left, y - 4, 300)
            elif ftype == "signature":
                pixel = draw_box(draw, box_left, y - 6, 420, 86)
            else:
                pixel = draw_box(draw, box_left, y - 6, box_width, 44)
        fields.append(field_gt(field_id, label, ftype, pixel))
        y += 110 if ftype != "signature" else 150

    # A couple of labels the dictionary genuinely does not know, so the sample also covers
    # the honest fallback rather than only the happy path.
    for label in spec["unknowable"]:
        if y > HEIGHT - 120:
            break
        if rtl:
            draw_text(image, draw, (WIDTH - margin, y), label, label_size, INK, anchor_right=True)
            draw_box(draw, margin, y - 6, WIDTH - 2 * margin - label_column, 44)
        else:
            draw_text(image, draw, (margin, y), label, label_size, INK)
            draw_box(draw, margin + label_column, y - 6, WIDTH - margin - margin - label_column, 44)
        y += 110

    footer = latin_font(16)
    draw.text((margin, HEIGHT - 40), "FormSathi synthetic sample - no real person or office", fill=(130, 140, 150), font=footer)
    return image, fields


def noisy(image: Image.Image, seed: int) -> Image.Image:
    """A scan taken in poor conditions: skewed, soft, dim, and speckled."""
    random.seed(seed)
    rng = np.random.default_rng(seed)
    out = image.rotate(random.uniform(-3.2, 3.2), expand=True, fillcolor=(236, 236, 234), resample=Image.BICUBIC)
    out = out.filter(ImageFilter.GaussianBlur(0.7))
    out = ImageEnhance.Brightness(out).enhance(0.9)
    out = ImageEnhance.Contrast(out).enhance(0.82)
    array = np.asarray(out).astype(np.int16)
    array += rng.normal(0, 7, array.shape).astype(np.int16)
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB")


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    GT.mkdir(parents=True, exist_ok=True)
    written = []
    for index, (code, spec) in enumerate(FORMS.items()):
        image, fields = build(spec)
        name = spec["name"]
        image.save(SAMPLES / f"{name}.png")
        noisy(image, seed=1000 + index).save(SAMPLES / f"{name}_noisy.png")
        (GT / f"{name}.json").write_text(
            json.dumps(
                {
                    "form_id": None,
                    "language": code,
                    "rtl": spec["rtl"],
                    "fields": fields,
                    "image": f"{name}.png",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        written.append(name)

    public = ROOT / "frontend" / "public" / "samples"
    public.mkdir(parents=True, exist_ok=True)
    for name in written:
        for suffix in ("", "_noisy"):
            source = SAMPLES / f"{name}{suffix}.png"
            (public / source.name).write_bytes(source.read_bytes())
    print(f"Wrote {len(written)} unknown-form samples (clean + noisy) to {SAMPLES}")
    for name in written:
        print(f"  {name}.png / {name}_noisy.png")


if __name__ == "__main__":
    main()
