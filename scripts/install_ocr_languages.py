"""Download Hindi, Kannada, and Urdu Tesseract models next to the backend.

The system install on a fresh Windows machine often has English only. Without these
models the other three scripts are not read, and their fields are missed.
"""

from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "backend" / "tessdata"
# The "best" models are slower and larger, and they are what makes Hindi, Kannada,
# and Urdu captions readable. The smaller "tessdata" set left relationship rows as
# garbage and merged the Urdu name block.
SOURCES = {
    "hin": "https://github.com/tesseract-ocr/tessdata_best/raw/main/hin.traineddata",
    "kan": "https://github.com/tesseract-ocr/tessdata_best/raw/main/kan.traineddata",
    "urd": "https://github.com/tesseract-ocr/tessdata_best/raw/main/urd.traineddata",
}
BEST_MIN_BYTES = 6_000_000
SYSTEM = Path(r"C:\Program Files\Tesseract-OCR\tessdata")


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for name in ("eng", "osd"):
        source = SYSTEM / f"{name}.traineddata"
        target = DEST / f"{name}.traineddata"
        if source.is_file() and not target.is_file():
            shutil.copyfile(source, target)
    for name, url in SOURCES.items():
        target = DEST / f"{name}.traineddata"
        if target.is_file() and target.stat().st_size > BEST_MIN_BYTES:
            print(f"{name} already present")
            continue
        print(f"downloading {name}")
        urllib.request.urlretrieve(url, target)
        print(f"{name} {target.stat().st_size} bytes")


if __name__ == "__main__":
    main()
