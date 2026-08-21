from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.services.rag_service import RAGService


def main() -> None:
    settings = get_settings()
    count = RAGService(settings).seed_knowledge_base()
    print(f"Indexed {count} knowledge-base chunks")


if __name__ == "__main__":
    main()
