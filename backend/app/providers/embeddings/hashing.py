from __future__ import annotations

import hashlib

import numpy as np


class HashingEmbeddingProvider:
    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            values = np.zeros(self.dimensions, dtype=np.float32)
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "little") % self.dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                values[index] += sign
            norm = float(np.linalg.norm(values)) or 1.0
            vectors.append((values / norm).tolist())
        return vectors
