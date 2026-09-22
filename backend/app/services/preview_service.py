from __future__ import annotations

import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.models.common import FieldType
from app.models.document import DocumentRecord
from app.models.fields import DetectedField, FieldAnswer
from app.models.preview import PreviewRequest, PreviewResult, PreviewWarning
from app.services.pdf_service import PdfService


FOOTER = "FormSathi Completed Reference Preview - Verify before copying or submitting."
SIGNATURE_MARK = "[SIGN MANUALLY]"


class PreviewService:
    def __init__(self, settings: Settings, pdf: PdfService) -> None:
        self.settings = settings
        self.pdf = pdf

    def render(self, record: DocumentRecord, request: PreviewRequest) -> PreviewResult:
        warnings: list[PreviewWarning] = []
        answers = {item.field_id: item for item in request.answers}
        page_images: list[Path] = []
        preview_id = str(uuid.uuid4())
        preview_dir = self.settings.previews_dir / record.id / preview_id
        preview_dir.mkdir(parents=True, exist_ok=True)

        for page in record.pages:
            source = Path(page.processed_path or page.original_path)
            image = Image.open(source).convert("RGB")
            draw = ImageDraw.Draw(image)
            font = self._font(max(16, image.width // 70))
            for field in record.fields:
                if field.page_index != page.index:
                    continue
                answer = answers.get(field.id)
                if answer is None or not answer.value:
                    continue
                warning = self._draw_field(draw, image, field, answer, font)
                if warning:
                    warnings.append(warning)
                    if warning.code == "text_overflow":
                        continue
            self._footer(draw, image, font)
            out = preview_dir / f"page-{page.index}.png"
            image.save(out)
            page_images.append(out)

        if warnings and any(item.code == "text_overflow" for item in warnings):
            return PreviewResult(preview_id=preview_id, warnings=warnings)

        pdf_path = preview_dir / "preview.pdf"
        self.pdf.write_pdf(page_images, pdf_path)
        return PreviewResult(
            preview_id=preview_id,
            pdf_path=str(pdf_path),
            image_paths=[str(path) for path in page_images],
            warnings=warnings,
        )

    def _draw_field(
        self,
        draw: ImageDraw.ImageDraw,
        image: Image.Image,
        field: DetectedField,
        answer: FieldAnswer,
        font: ImageFont.ImageFont,
    ) -> PreviewWarning | None:
        box = field.input_box.to_pixel(image.width, image.height)
        left, top = box.x + 3, box.y + 2
        if field.field_type == FieldType.SIGNATURE:
            draw.text((left, top), SIGNATURE_MARK, fill=(20, 40, 70), font=font)
            return None
        if field.field_type in {FieldType.CHECKBOX, FieldType.RADIO}:
            if answer.value.lower() in {"true", "1", "yes", "on", "x"}:
                draw.line((box.x + 2, box.y + 2, box.x + box.width - 2, box.y + box.height - 2), fill=(20, 40, 70), width=3)
                draw.line((box.x + box.width - 2, box.y + 2, box.x + 2, box.y + box.height - 2), fill=(20, 40, 70), width=3)
            return None
        text = answer.value.strip()
        wrapped = self._wrap(text, font, box.width - 8)
        line_height = int(font.size * 1.2)
        if len(wrapped) * line_height > box.height + 6:
            return PreviewWarning(field_id=field.id, code="text_overflow", message="Text does not fit this field. Shorten it.")
        y = top
        for line in wrapped:
            draw.text((left, y), line, fill=(20, 40, 70), font=font)
            y += line_height
        return None

    def _wrap(self, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if font.getlength(trial) <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [text]

    def _footer(self, draw: ImageDraw.ImageDraw, image: Image.Image, font: ImageFont.ImageFont) -> None:
        draw.rectangle((0, image.height - 28, image.width, image.height), fill=(245, 247, 250))
        draw.text((10, image.height - 24), FOOTER, fill=(70, 80, 95), font=font)

    def _font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in candidates:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()
