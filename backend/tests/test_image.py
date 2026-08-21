from pathlib import Path

from PIL import Image

from app.services.image_service import ImageService


def test_preprocess_creates_processed_image(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (400, 500), (240, 240, 240)).save(source)
    destination = tmp_path / "processed.png"
    result = ImageService().preprocess(str(source), str(destination))
    assert Path(result.processed_path).exists()
    assert result.original_width == 400
    assert result.processed_width > 0
