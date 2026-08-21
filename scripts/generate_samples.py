from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


MEDICINE_LINES = [
    "PARACETAMOL TABLETS",
    "500 mg",
    "",
    "Batch: ABC123",
    "MFG: JAN 2026",
    "EXP: DEC 2027",
    "",
    "Dosage: As directed by physician.",
    "Store below 25 C.",
    "Keep out of reach of children.",
]

BILL_LINES = [
    "ELECTRICITY BILL",
    "",
    "Account Number: 12345678",
    "Bill Amount: Rs 2450",
    "Due Date: 25 September 2026",
    "Units Consumed: 180 kWh",
    "Please pay before the due date.",
]


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def render_label(lines: list[str], path: Path, title_size: int = 42) -> Path:
    width, height = 900, 1200
    image = Image.new("RGB", (width, height), (252, 250, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, width - 40, height - 40), outline=(30, 64, 70), width=4)
    y = 90
    for index, line in enumerate(lines):
        font = _font(title_size if index == 0 else 32)
        draw.text((80, y), line, fill=(22, 32, 38), font=font)
        y += 58 if line else 28
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def generate_all(output_dir: Path | None = None) -> dict[str, Path]:
    root = output_dir or Path(__file__).resolve().parent.parent / "samples"
    medicine = render_label(MEDICINE_LINES, root / "medicine_label.png")
    bill = render_label(BILL_LINES, root / "electricity_bill.png", title_size=40)
    return {"medicine": medicine, "bill": bill}


if __name__ == "__main__":
    paths = generate_all()
    for key, value in paths.items():
        print(f"{key}: {value}")
