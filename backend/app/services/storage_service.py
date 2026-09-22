from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.config import Settings


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def save_upload(self, payload: bytes, suffix: str) -> Path:
        safe_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        path = self.settings.uploads_dir / f"{uuid4().hex}{safe_suffix}"
        path.write_bytes(payload)
        return path

    def processed_page_path(self, document_id: str, page_index: int) -> Path:
        directory = self.settings.processed_dir / document_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"page-{page_index}.png"

    def delete_tree(self, *paths: str | Path | None) -> None:
        for item in paths:
            if not item:
                continue
            path = Path(item)
            if path.is_dir():
                for child in path.rglob("*"):
                    if child.is_file():
                        child.unlink(missing_ok=True)
                for child in sorted(path.rglob("*"), reverse=True):
                    if child.is_dir():
                        child.rmdir()
                path.rmdir() if path.exists() else None
            elif path.exists():
                path.unlink(missing_ok=True)
