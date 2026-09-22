from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.dependencies import build_container


def main() -> None:
    settings = get_settings()
    container = build_container(settings)
    container.knowledge.reload()
    container.retrieval.seed()
    print(f"Indexed {len(container.knowledge.field_chunks())} field chunks using {container.vectors.backend}")


if __name__ == "__main__":
    main()
