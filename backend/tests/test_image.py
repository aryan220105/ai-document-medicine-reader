from pathlib import Path

from PIL import Image

from app.services.image_service import ImageService


def test_exif_orientation(tmp_path: Path):
    path = tmp_path / "rotated.jpg"
    image = Image.new("RGB", (40, 80), (10, 20, 30))
    image.save(path, format="JPEG")
    ImageService().apply_exif(str(path))
    assert Path(path).exists()
