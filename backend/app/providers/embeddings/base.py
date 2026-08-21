from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def available(self) -> bool:
        ...
