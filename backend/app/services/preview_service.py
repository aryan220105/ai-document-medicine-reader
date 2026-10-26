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
from app.utils import text_shaping
from app.utils.text_normalization import dominant_script


FOOTER = "FormSathi Completed Reference Preview - Verify before copying or submitting."
SIGNATURE_MARK = "[SIGN MANUALLY]"


def centered_x(box_x: float, box_width: float, text_width: float) -> float:
    return box_x + max(0.0, (box_width - text_width) / 2)


def centered_y(box_y: float, box_height: float, block_height: float) -> float:
    return box_y + max(0.0, (box_height - block_height) / 2)


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
        if field.field_type == FieldType.SIGNATURE:
            mark_width = font.getlength(SIGNATURE_MARK)
            draw.text(
                (centered_x(box.x, box.width, mark_width), centered_y(box.y, box.height, font.size)),
                SIGNATURE_MARK,
                fill=(20, 40, 70),
                font=font,
            )
            return None
        if field.field_type in {FieldType.CHECKBOX, FieldType.RADIO}:
            if answer.value.lower() in {"true", "1", "yes", "on", "x"}:
                draw.line((box.x + 2, box.y + 2, box.x + box.width - 2, box.y + box.height - 2), fill=(20, 40, 70), width=3)
                draw.line((box.x + box.width - 2, box.y + 2, box.x + 2, box.y + box.height - 2), fill=(20, 40, 70), width=3)
            return None
        text = answer.value.strip()
        script = dominant_script(text)
        if script not in {"latin", "unknown"}:
            return self._draw_shaped(image, field, text, script, box, font.size)
        wrapped = self._wrap(text, font, box.width - 8)
        line_height = int(font.size * 1.2)
        block_height = len(wrapped) * line_height
        if block_height > box.height + 6:
            return PreviewWarning(field_id=field.id, code="text_overflow", message="Text does not fit this field. Shorten it.")
        y = centered_y(box.y, box.height, block_height)
        for line in wrapped:
            line_width = font.getlength(line)
            draw.text((centered_x(box.x, box.width, line_width), y), line, fill=(20, 40, 70), font=font)
            y += line_height
        return None

    def _draw_shaped(
        self,
        image: Image.Image,
        field: DetectedField,
        text: str,
        script: str,
        box,
        size: int,
    ) -> PreviewWarning | None:
        """Draw an answer written in Devanagari, Kannada, or Urdu.

        Pillow cannot shape these scripts in a default install, so the text is shaped with
        HarfBuzz. If shaping is unavailable the answer is left off the sheet and a warning
        is raised, because a misordered rendering of someone's own name is worse than a
        gap they can fill in by hand.
        """
        if not text_shaping.can_shape(text):
            return PreviewWarning(
                field_id=field.id,
                code="script_not_rendered",
                message=(
                    f"This answer is written in the {script} script, which cannot be rendered on this "
                    "machine. Install the shaping extras, or copy this value onto the form directly."
                ),
            )
        rendered = text_shaping.render_line(text, size)
        if rendered is None:
            return PreviewWarning(
                field_id=field.id,
                code="script_not_rendered",
                message="This answer could not be rendered. Copy it onto the form directly.",
            )
        if rendered.width > box.width - 6 or rendered.height > box.height + 8:
            return PreviewWarning(
                field_id=field.id,
                code="text_overflow",
                message="Text does not fit this field. Shorten it.",
            )
        image.paste(
            rendered.image,
            (int(centered_x(box.x, box.width, rendered.width)), int(centered_y(box.y, box.height, rendered.height))),
            rendered.image,
        )
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
