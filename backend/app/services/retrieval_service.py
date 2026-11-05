from __future__ import annotations

from typing import Any

from app.models.common import Language
from app.repositories.field_dictionary_repository import FieldDictionaryRepository
from app.repositories.form_knowledge_repository import FormKnowledgeRepository
from app.repositories.vector_repository import VectorRepository


class RetrievalService:
    def __init__(
        self,
        knowledge: FormKnowledgeRepository,
        vectors: VectorRepository,
        dictionary: FieldDictionaryRepository | None = None,
    ) -> None:
        self.knowledge = knowledge
        self.vectors = vectors
        self.dictionary = dictionary

    def seed(self) -> None:
        """Index the known forms and the common-field dictionary together.

        Indexing the dictionary is what gives retrieval anything to say about an unknown
        form: without it the vector store only knows the four seeded demo forms.
        """
        chunks = self.knowledge.field_chunks()
        if self.dictionary is not None:
            chunks.extend(self.dictionary.chunks())
        self.vectors.replace_chunks(chunks)

    def retrieve(self, query: str, language: Language, form_id: str | None = None) -> list[dict[str, Any]]:
        where = {"language": language.value}
        if form_id:
            where["form_id"] = form_id
        hits = self.vectors.query(query, n_results=5, where=where)
        if hits or not form_id:
            return hits
        # A recognised form that has nothing to say about this particular field: fall back
        # to the language-wide index so the common dictionary can still answer.
        return self.vectors.query(query, n_results=5, where={"language": language.value})
