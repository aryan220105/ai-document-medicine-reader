from __future__ import annotations

import logging
from hashlib import sha256

import numpy as np

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddings:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None
        self._failed = False

    def available(self) -> bool:
        return self._load() is not None

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        if model is None:
            return HashingEmbeddings().embed(texts)
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [vector.tolist() for vector in np.asarray(vectors)]

    def _load(self):
        if self._failed:
            return None
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            return self._model
        except Exception:
            logger.warning("Sentence-transformers unavailable; using hashing embeddings")
            self._failed = True
            return None


class HashingEmbeddings:
    """Deterministic fallback embeddings so RAG still runs without the model download."""

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = np.zeros(self.dimensions, dtype=np.float32)
        tokens = (text or "").lower().split()
        if not tokens:
            return vector.tolist()
        for token in tokens:
            digest = sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = np.linalg.norm(vector)
        if norm:
            vector /= norm
        return vector.tolist()
