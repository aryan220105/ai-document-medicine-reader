from __future__ import annotations

from typing import Any

from app.models.common import Language
from app.repositories.form_knowledge_repository import FormKnowledgeRepository
from app.repositories.vector_repository import VectorRepository


class RetrievalService:
    def __init__(self, knowledge: FormKnowledgeRepository, vectors: VectorRepository) -> None:
        self.knowledge = knowledge
        self.vectors = vectors

    def seed(self) -> None:
        self.vectors.replace_chunks(self.knowledge.field_chunks())

    def retrieve(self, query: str, language: Language, form_id: str | None = None) -> list[dict[str, Any]]:
        where = {"language": language.value}
        if form_id:
            where["form_id"] = form_id
        return self.vectors.query(query, n_results=5, where=where)
