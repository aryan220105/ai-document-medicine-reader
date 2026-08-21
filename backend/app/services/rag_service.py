from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

import numpy as np

from app.config import Settings
from app.models.document import KnowledgeChunk, RetrievalResult
from app.models.ocr import OCRResult, OCRWord
from app.providers.embeddings.sentence_transformer import (
    HashingEmbeddings,
    SentenceTransformerEmbeddings,
)
from app.utils.text import normalize_text

logger = logging.getLogger(__name__)

KNOWLEDGE_COLLECTION = "knowledge_base"
DOCUMENT_COLLECTION = "documents"


class _MemoryCollection:
    def __init__(self) -> None:
        self.ids: list[str] = []
        self.documents: list[str] = []
        self.embeddings: list[list[float]] = []
        self.metadatas: list[dict[str, str]] = []

    def count(self) -> int:
        return len(self.ids)

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str]],
    ) -> None:
        for index, item_id in enumerate(ids):
            if item_id in self.ids:
                existing = self.ids.index(item_id)
                self.documents[existing] = documents[index]
                self.embeddings[existing] = embeddings[index]
                self.metadatas[existing] = metadatas[index]
            else:
                self.ids.append(item_id)
                self.documents.append(documents[index])
                self.embeddings.append(embeddings[index])
                self.metadatas.append(metadatas[index])

    def delete(self, where: dict[str, str] | None = None) -> None:
        if not where:
            self.ids.clear()
            self.documents.clear()
            self.embeddings.clear()
            self.metadatas.clear()
            return
        keep = []
        for index, metadata in enumerate(self.metadatas):
            if all(str(metadata.get(key)) == str(value) for key, value in where.items()):
                continue
            keep.append(index)
        self.ids = [self.ids[i] for i in keep]
        self.documents = [self.documents[i] for i in keep]
        self.embeddings = [self.embeddings[i] for i in keep]
        self.metadatas = [self.metadatas[i] for i in keep]

    def query(self, query_embeddings: list[list[float]], n_results: int, where: dict[str, str] | None = None):
        query = np.array(query_embeddings[0], dtype=np.float32)
        selected = list(range(len(self.ids)))
        if where:
            selected = [
                index
                for index, metadata in enumerate(self.metadatas)
                if all(str(metadata.get(key)) == str(value) for key, value in where.items())
            ]
        if not selected:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        matrix = np.array([self.embeddings[i] for i in selected], dtype=np.float32)
        denom = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(query) or 1.0)
        denom = np.where(denom == 0, 1.0, denom)
        scores = matrix @ query / denom
        order = np.argsort(-scores)[:n_results]
        picked = [selected[int(i)] for i in order]
        return {
            "ids": [[self.ids[i] for i in picked]],
            "documents": [[self.documents[i] for i in picked]],
            "metadatas": [[self.metadatas[i] for i in picked]],
            "distances": [[float(1.0 - scores[int(i)]) for i in order]],
        }


class _MemoryClient:
    def __init__(self) -> None:
        self.collections: dict[str, _MemoryCollection] = {}

    def get_or_create_collection(self, name: str, metadata: dict | None = None) -> _MemoryCollection:
        return self.collections.setdefault(name, _MemoryCollection())

    def delete_collection(self, name: str) -> None:
        self.collections.pop(name, None)


class RAGService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embedder = SentenceTransformerEmbeddings(settings.embedding_model)
        self.fallback = HashingEmbeddings()
        self._client = None
        self._knowledge_ready = False

    def available(self) -> bool:
        try:
            self._store()
            return True
        except Exception:
            logger.exception("Vector store unavailable")
            return False

    def seed_knowledge_base(self) -> int:
        directory = Path(self.settings.knowledge_base_dir)
        if not directory.exists():
            return 0
        chunks: list[KnowledgeChunk] = []
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
            for index, paragraph in enumerate(paragraphs):
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=f"{path.stem}-{index}",
                        text=paragraph,
                        source=path.name,
                        title=path.stem.replace("_", " ").title(),
                    )
                )
        self._replace_collection(KNOWLEDGE_COLLECTION, chunks, source_type="knowledge_base")
        self._knowledge_ready = True
        logger.info("Indexed %s knowledge-base chunks", len(chunks))
        return len(chunks)

    def index_document(self, document_id: str, ocr: OCRResult) -> int:
        chunks = self._chunk_ocr(document_id, ocr)
        self._upsert(DOCUMENT_COLLECTION, chunks, source_type="uploaded_document")
        return len(chunks)

    def delete_document(self, document_id: str) -> None:
        collection = self._collection(DOCUMENT_COLLECTION)
        try:
            collection.delete(where={"document_id": document_id})
        except Exception:
            logger.warning("Could not delete vectors for document %s", document_id)

    def retrieve_document(self, question: str, document_id: str, limit: int = 6) -> list[RetrievalResult]:
        return self._query(DOCUMENT_COLLECTION, question, limit=limit, where={"document_id": document_id})

    def retrieve_knowledge(self, question: str, limit: int = 4) -> list[RetrievalResult]:
        if not self._knowledge_ready:
            self.seed_knowledge_base()
        return self._query(KNOWLEDGE_COLLECTION, question, limit=limit)

    def _chunk_ocr(self, document_id: str, ocr: OCRResult) -> list[KnowledgeChunk]:
        lines: dict[int, list[OCRWord]] = {}
        for word in ocr.words:
            lines.setdefault(word.line_id, []).append(word)
        ordered_line_ids = sorted(lines)
        chunks: list[KnowledgeChunk] = []
        step = 2
        for index in range(0, len(ordered_line_ids), step):
            group_ids = ordered_line_ids[index: index + 3]
            group_words: list[OCRWord] = []
            texts: list[str] = []
            for line_id in group_ids:
                line_words = sorted(lines[line_id], key=lambda item: item.x)
                group_words.extend(line_words)
                texts.append(" ".join(word.text for word in line_words))
            text = normalize_text(" ".join(texts))
            if len(text) < 8:
                continue
            word_ids = [str(word.id) for word in group_words]
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{document_id}-{index}",
                    text=text,
                    source="uploaded_document",
                    metadata={
                        "document_id": document_id,
                        "word_ids": ",".join(word_ids),
                        "line_ids": ",".join(str(item) for item in group_ids),
                    },
                )
            )
        if not chunks and ocr.full_text.strip():
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{document_id}-full",
                    text=ocr.full_text.strip(),
                    source="uploaded_document",
                    metadata={"document_id": document_id, "word_ids": ""},
                )
            )
        return chunks

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self.settings.app_env == "test" or self.settings.use_light_embeddings:
            return self.fallback.embed(texts)
        if self.embedder.available():
            return self.embedder.embed(texts)
        return self.fallback.embed(texts)

    def _store(self):
        if self._client is not None:
            return self._client
        try:
            import chromadb

            self._client = chromadb.PersistentClient(path=str(self.settings.chroma_dir))
            self._client.get_or_create_collection(KNOWLEDGE_COLLECTION)
            return self._client
        except Exception:
            logger.warning("ChromaDB unavailable; using in-memory vector store")
            self._client = _MemoryClient()
            return self._client

    def _collection(self, name: str):
        return self._store().get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})

    def _replace_collection(self, name: str, chunks: list[KnowledgeChunk], source_type: str) -> None:
        client = self._store()
        try:
            client.delete_collection(name)
        except Exception:
            pass
        self._upsert(name, chunks, source_type=source_type)

    def _upsert(self, name: str, chunks: list[KnowledgeChunk], source_type: str) -> None:
        if not chunks:
            return
        collection = self._collection(name)
        embeddings = self._embed([chunk.text for chunk in chunks])
        collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "source": chunk.source,
                    "source_type": source_type,
                    "title": chunk.title,
                    **chunk.metadata,
                }
                for chunk in chunks
            ],
        )

    def _query(
        self,
        name: str,
        question: str,
        limit: int,
        where: dict[str, str] | None = None,
    ) -> list[RetrievalResult]:
        collection = self._collection(name)
        if collection.count() == 0:
            return []
        query_kwargs = {
            "query_embeddings": self._embed([question]),
            "n_results": min(limit, max(collection.count(), 1)),
        }
        if where:
            query_kwargs["where"] = where
        result = collection.query(**query_kwargs)
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        ids = (result.get("ids") or [[]])[0]
        retrieved: list[RetrievalResult] = []
        for index, text in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else 1.0
            word_ids = []
            raw_ids = str(metadata.get("word_ids") or "")
            if raw_ids:
                word_ids = [int(part) for part in raw_ids.split(",") if part.isdigit()]
            retrieved.append(
                RetrievalResult(
                    chunk_id=ids[index] if index < len(ids) else str(uuid4()),
                    text=text,
                    source=str(metadata.get("source") or name),
                    score=round(1.0 - float(distance), 4),
                    word_ids=word_ids,
                    metadata={str(key): str(value) for key, value in metadata.items()},
                )
            )
        return retrieved
