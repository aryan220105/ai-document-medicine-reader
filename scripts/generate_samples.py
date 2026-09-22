from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
GT = SAMPLES / "ground_truth"
sys.path.insert(0, str(ROOT / "backend"))


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def box(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    draw.rectangle((x, y, x + w, y + h), outline=(30, 45, 70), width=2)
    return (x, y, w, h)


def underline(draw: ImageDraw.ImageDraw, x: int, y: int, w: int) -> tuple[int, int, int, int]:
    draw.line((x, y + 28, x + w, y + 28), fill=(30, 45, 70), width=2)
    return (x, y, w, 32)


def checkbox(draw: ImageDraw.ImageDraw, x: int, y: int) -> tuple[int, int, int, int]:
    draw.rectangle((x, y, x + 18, y + 18), outline=(30, 45, 70), width=2)
    return (x, y, 18, 18)


def radio(draw: ImageDraw.ImageDraw, x: int, y: int) -> tuple[int, int, int, int]:
    draw.ellipse((x, y, x + 16, y + 16), outline=(30, 45, 70), width=2)
    return (x, y, 16, 16)


def field_gt(field_id: str, label: str, ftype: str, pixel: tuple[int, int, int, int], options: list[str] | None = None) -> dict:
    x, y, w, h = pixel
    return {
        "field_id": field_id,
        "label": label,
        "type": ftype,
        "pixel": {"x": x, "y": y, "width": w, "height": h, "image_width": 1240, "image_height": 1754},
        "options": options or [],
    }


def header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    title_font = font(32)
    body = font(18)
    draw.text((64, 48), title, fill=(18, 36, 64), font=title_font)
    draw.text((64, 92), subtitle, fill=(70, 82, 98), font=body)
    draw.text((64, 118), "SYNTHETIC DEMO FORM - Not an official document", fill=(140, 60, 40), font=font(16))


def save(image: Image.Image, name: str, fields: list[dict], form_id: str | None) -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    GT.mkdir(parents=True, exist_ok=True)
    clean = SAMPLES / f"{name}.png"
    image.save(clean)
    noisy = image.rotate(3, expand=True, fillcolor=(235, 235, 235)).convert("RGB")
    noisy = ImageEnhance.Brightness(noisy).enhance(0.92)
    noisy = ImageEnhance.Contrast(noisy).enhance(0.88)
    noisy.save(SAMPLES / f"{name}_noisy.png")
    (GT / f"{name}.json").write_text(
        json.dumps({"form_id": form_id, "fields": fields, "image": f"{name}.png"}, indent=2),
        encoding="utf-8",
    )


def bank() -> None:
    image = Image.new("RGB", (1240, 1754), (248, 249, 252))
    draw = ImageDraw.Draw(image)
    header(draw, "Demo Bank Account Opening Form", "Demo Sathi Cooperative Bank")
    body = font(20)
    y = 180
    fields = []
    draw.text((64, y), "Name of Applicant", fill=(20, 30, 45), font=body)
    fields.append(field_gt("full_name", "Name of Applicant", "text", box(draw, 360, y - 6, 740, 40)))
    y = 260
    draw.text((64, y), "Date of Birth", fill=(20, 30, 45), font=body)
    fields.append(field_gt("date_of_birth", "Date of Birth", "date", underline(draw, 360, y - 4, 280)))
    y = 340
    draw.text((64, y), "Occupation", fill=(20, 30, 45), font=body)
    fields.append(field_gt("occupation", "Occupation", "text", box(draw, 360, y - 6, 740, 40)))
    y = 420
    draw.text((64, y), "Nominee", fill=(20, 30, 45), font=body)
    fields.append(field_gt("nominee", "Nominee", "text", box(draw, 360, y - 6, 740, 40)))
    y = 510
    draw.text((64, y), "Account Type", fill=(20, 30, 45), font=body)
    savings = checkbox(draw, 360, y)
    draw.text((390, y - 2), "Savings", fill=(20, 30, 45), font=body)
    current = checkbox(draw, 560, y)
    draw.text((590, y - 2), "Current", fill=(20, 30, 45), font=body)
    fields.append(field_gt("account_type", "Account Type", "checkbox", savings, ["Savings", "Current"]))
    y = 600
    draw.text((64, y), "Residential Address", fill=(20, 30, 45), font=body)
    fields.append(field_gt("address", "Residential Address", "multiline", box(draw, 64, y + 36, 1036, 120)))
    y = 800
    draw.rectangle((64, y, 1100, y + 160), outline=(180, 188, 200), width=1)
    draw.text((80, y + 16), "For office use", fill=(90, 100, 110), font=font(16))
    draw.text((80, y + 50), "Reference", fill=(20, 30, 45), font=body)
    draw.text((80, y + 96), "Date", fill=(20, 30, 45), font=body)
    y = 1020
    draw.text((64, y), "Applicant Signature / Sign here", fill=(20, 30, 45), font=body)
    fields.append(field_gt("signature", "Applicant Signature", "signature", box(draw, 64, y + 36, 420, 90)))
    save(image, "demo_bank_account_opening", fields, "demo_bank_account_opening_v1")


def scholarship() -> None:
    image = Image.new("RGB", (1240, 1754), (250, 248, 245))
    draw = ImageDraw.Draw(image)
    header(draw, "Demo Scholarship Application Form", "Demo Education Trust")
    body = font(20)
    rows = [
        ("Student Name", 180, "full_name", "text"),
        ("Date of Birth", 260, "date_of_birth", "date"),
        ("Institution", 340, "institution", "text"),
        ("Course Name", 420, "course_name", "text"),
        ("Marks Obtained", 500, "marks", "text"),
    ]
    fields = []
    for label, y, field_id, ftype in rows:
        draw.text((64, y), label, fill=(20, 30, 45), font=body)
        fields.append(field_gt(field_id, label, ftype, box(draw, 360, y - 6, 740, 40)))
    y = 590
    draw.text((64, y), "Declaration", fill=(20, 30, 45), font=body)
    cb = checkbox(draw, 360, y)
    draw.text((390, y - 2), "I confirm the printed details are correct", fill=(20, 30, 45), font=body)
    fields.append(field_gt("declaration", "Declaration", "checkbox", cb, ["I confirm"]))
    y = 700
    draw.text((64, y), "Student Signature", fill=(20, 30, 45), font=body)
    fields.append(field_gt("signature", "Student Signature", "signature", box(draw, 64, y + 36, 420, 90)))
    save(image, "demo_scholarship_application", fields, "demo_scholarship_application_v1")


def insurance() -> None:
    image = Image.new("RGB", (1240, 1754), (245, 248, 250))
    draw = ImageDraw.Draw(image)
    header(draw, "Demo Insurance Nominee Form", "Demo Shield Insurance")
    body = font(20)
    fields = []
    items = [
        ("Policyholder Name", 180, "policyholder_name", "text"),
        ("Policy Number", 260, "policy_number", "text"),
        ("Nominee Name", 340, "nominee", "text"),
        ("Relationship", 420, "relationship", "text"),
        ("Share Percent", 500, "share_percent", "text"),
        ("Date of Birth", 580, "date_of_birth", "date"),
    ]
    for label, y, field_id, ftype in items:
        draw.text((64, y), label, fill=(20, 30, 45), font=body)
        kind = underline if ftype == "date" else box
        pixel = kind(draw, 400, y - 4, 700) if ftype == "date" else box(draw, 400, y - 6, 700, 40)
        fields.append(field_gt(field_id, label, ftype, pixel))
    y = 700
    draw.text((64, y), "Sign here", fill=(20, 30, 45), font=body)
    fields.append(field_gt("signature", "Sign here", "signature", box(draw, 64, y + 36, 420, 90)))
    save(image, "demo_insurance_nominee", fields, "demo_insurance_nominee_v1")


def government() -> None:
    image = Image.new("RGB", (1240, 1754), (247, 250, 247))
    draw = ImageDraw.Draw(image)
    header(draw, "Demo Basic Government Service Application", "Demo Civic Office")
    body = font(20)
    fields = []
    draw.text((64, 180), "Applicant Name", fill=(20, 30, 45), font=body)
    fields.append(field_gt("full_name", "Applicant Name", "text", box(draw, 360, 174, 740, 40)))
    draw.text((64, 260), "Residential Address", fill=(20, 30, 45), font=body)
    fields.append(field_gt("address", "Residential Address", "multiline", box(draw, 64, 296, 1036, 110)))
    draw.text((64, 440), "Ward Number", fill=(20, 30, 45), font=body)
    fields.append(field_gt("ward_number", "Ward Number", "text", box(draw, 360, 434, 200, 40)))
    draw.text((64, 520), "Service Requested", fill=(20, 30, 45), font=body)
    water = radio(draw, 360, 524)
    draw.text((386, 520), "Water", fill=(20, 30, 45), font=body)
    light = radio(draw, 520, 524)
    draw.text((546, 520), "Street light", fill=(20, 30, 45), font=body)
    fields.append(field_gt("service_requested", "Service Requested", "radio", water, ["Water", "Street light"]))
    draw.text((64, 600), "Contact Number", fill=(20, 30, 45), font=body)
    fields.append(field_gt("contact_number", "Contact Number", "text", box(draw, 360, 594, 400, 40)))
    draw.text((64, 680), "Acknowledgement", fill=(20, 30, 45), font=body)
    ack = checkbox(draw, 360, 684)
    draw.text((390, 680), "I understand this is a demonstration form", fill=(20, 30, 45), font=body)
    fields.append(field_gt("acknowledgement", "Acknowledgement", "checkbox", ack, ["I understand"]))
    draw.text((64, 800), "Applicant Signature", fill=(20, 30, 45), font=body)
    fields.append(field_gt("signature", "Applicant Signature", "signature", box(draw, 64, 836, 420, 90)))
    save(image, "demo_government_service", fields, "demo_government_service_v1")


def unknown() -> None:
    image = Image.new("RGB", (1240, 1400), (252, 250, 246))
    draw = ImageDraw.Draw(image)
    header(draw, "Demo Community Library Card Request", "Unknown to the knowledge base")
    body = font(20)
    fields = []
    draw.text((64, 180), "Full Name", fill=(20, 30, 45), font=body)
    fields.append(field_gt("full_name", "Full Name", "text", box(draw, 360, 174, 740, 40)))
    draw.text((64, 260), "Date of Birth", fill=(20, 30, 45), font=body)
    fields.append(field_gt("date_of_birth", "Date of Birth", "date", underline(draw, 360, 256, 300)))
    draw.text((64, 340), "Favourite Genre", fill=(20, 30, 45), font=body)
    fields.append(field_gt("favourite_genre", "Favourite Genre", "text", box(draw, 360, 334, 740, 40)))
    draw.text((64, 420), "Membership Code", fill=(20, 30, 45), font=body)
    fields.append(field_gt("membership_code", "Membership Code", "text", box(draw, 360, 414, 400, 40)))
    save(image, "demo_unknown_library_card", fields, None)


def main() -> None:
    bank()
    scholarship()
    insurance()
    government()
    unknown()
    public = ROOT / "frontend" / "public" / "samples"
    public.mkdir(parents=True, exist_ok=True)
    for image in SAMPLES.glob("*.png"):
        target = public / image.name
        target.write_bytes(image.read_bytes())
    (SAMPLES / "README.md").write_text(
        "# Synthetic FormSathi samples\n\n"
        "All files are original demonstration forms. They are not copies of official documents.\n"
        "Each clean PNG has a `_noisy` rotated variant and a ground-truth JSON file.\n",
        encoding="utf-8",
    )
    print(f"Wrote samples to {SAMPLES}")


if __name__ == "__main__":
    main()
