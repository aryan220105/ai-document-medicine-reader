from __future__ import annotations

from pathlib import Path

from PIL import Image


class PdfService:
    def render_pages(self, source: Path, destination_dir: Path, max_pages: int) -> list[Path]:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PDF support requires PyMuPDF (pymupdf).") from exc
        document = fitz.open(source)
        if document.is_encrypted:
            document.close()
            raise ValueError("This PDF is encrypted. Please upload an unlocked copy.")
        if document.page_count < 1:
            document.close()
            raise ValueError("The PDF has no readable pages.")
        if document.page_count > max_pages:
            document.close()
            raise ValueError(f"Please upload a PDF with at most {max_pages} pages.")
        destination_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            path = destination_dir / f"page-{index}.png"
            pixmap.save(str(path))
            paths.append(path)
        document.close()
        return paths

    def write_pdf(self, images: list[Path], destination: Path) -> None:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PDF support requires PyMuPDF (pymupdf).") from exc
        document = fitz.open()
        for image_path in images:
            image = Image.open(image_path)
            width, height = image.size
            page = document.new_page(width=width, height=height)
            page.insert_image(page.rect, filename=str(image_path))
        destination.parent.mkdir(parents=True, exist_ok=True)
        document.save(destination)
        document.close()
