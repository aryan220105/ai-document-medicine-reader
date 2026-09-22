from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.providers.embeddings.hashing import HashingEmbeddingProvider
from app.utils.text_normalization import fold, tokens

logger = logging.getLogger(__name__)


class VectorRepository:
    def __init__(self, settings: Settings, embeddings: HashingEmbeddingProvider) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self._collection = None
        self._lexical: list[dict[str, Any]] = []
        self.backend = "lexical"
        self._init_chroma()

    def _init_chroma(self) -> None:
        if self.settings.vector_store != "chroma":
            return
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            client = chromadb.PersistentClient(
                path=str(self.settings.chroma_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = client.get_or_create_collection("formsathi_fields")
            self.backend = "chroma"
        except Exception:
            logger.warning("ChromaDB unavailable; using lexical retrieval")
            self._collection = None
            self.backend = "lexical"

    def replace_chunks(self, chunks: list[dict[str, Any]]) -> None:
        self._lexical = chunks
        if self._collection is None:
            return
        try:
            existing = self._collection.get()
            if existing and existing.get("ids"):
                self._collection.delete(ids=existing["ids"])
            texts = [chunk["text"] for chunk in chunks]
            vectors = self.embeddings.embed(texts)
            self._collection.add(
                ids=[chunk["id"] for chunk in chunks],
                documents=texts,
                embeddings=vectors,
                metadatas=[self._safe_metadata(chunk["metadata"]) for chunk in chunks],
            )
        except Exception:
            logger.warning("Vector indexing failed; lexical fallback remains active")
            self.backend = "lexical"

    def query(self, text: str, n_results: int = 5, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if self._collection is not None and self.backend == "chroma":
            try:
                query = {"query_embeddings": self.embeddings.embed([text]), "n_results": n_results}
                if where:
                    query["where"] = where
                result = self._collection.query(**query)
                hits: list[dict[str, Any]] = []
                for index, chunk_id in enumerate(result.get("ids", [[]])[0]):
                    distance = (result.get("distances") or [[1]])[0][index]
                    score = max(0.0, 1.0 - float(distance))
                    metadata = (result.get("metadatas") or [[{}]])[0][index] or {}
                    hits.append({"id": chunk_id, "score": score, "metadata": metadata, "backend": "chroma"})
                return hits
            except Exception:
                logger.warning("Chroma query failed; using lexical fallback")
        return self._lexical_query(text, n_results)

    def _lexical_query(self, text: str, n_results: int) -> list[dict[str, Any]]:
        query_tokens = set(tokens(fold(text)))
        scored: list[dict[str, Any]] = []
        for chunk in self._lexical:
            chunk_tokens = set(tokens(fold(chunk["text"])))
            if not query_tokens or not chunk_tokens:
                continue
            score = len(query_tokens & chunk_tokens) / len(query_tokens | chunk_tokens)
            if score > 0:
                scored.append({"id": chunk["id"], "score": score, "metadata": chunk["metadata"], "backend": "lexical"})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:n_results]

    @staticmethod
    def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                safe[key] = value
            elif isinstance(value, list):
                safe[key] = ", ".join(str(item) for item in value)
            elif isinstance(value, dict):
                safe[key] = str(value)
        return safe
