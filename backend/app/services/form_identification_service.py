from __future__ import annotations

from app.config import Settings
from app.models.common import DocumentCategory
from app.models.document import KnownFormMatch
from app.models.fields import DetectedField
from app.models.ocr import OCRResult
from app.repositories.form_knowledge_repository import FormKnowledgeRepository
from app.utils.text_normalization import fold


class FormIdentificationService:
    def __init__(self, knowledge: FormKnowledgeRepository, settings: Settings) -> None:
        self.knowledge = knowledge
        self.settings = settings

    def match(
        self,
        ocr_pages: list[OCRResult],
        fields: list[DetectedField],
        category: DocumentCategory,
    ) -> KnownFormMatch:
        corpus = fold(" ".join(page.full_text for page in ocr_pages))
        labels = {fold(field.label) for field in fields if field.label}
        best: KnownFormMatch | None = None
        for form in self.knowledge.all_forms():
            terms = [fold(term) for term in form.get("fingerprint_terms", [])]
            matched_terms = [term for term in terms if term and term in corpus]
            term_score = len(matched_terms) / max(len(terms), 1)
            aliases = {fold(alias) for field in form.get("fields", []) for alias in field.get("aliases", [])}
            label_hits = sum(1 for label in labels if any(alias in label or label in alias for alias in aliases))
            label_score = label_hits / max(len(aliases), 1)
            category_bonus = 0.12 if form.get("category") == category.value else 0.0
            score = min(1.0, 0.55 * term_score + 0.4 * label_score + category_bonus)
            candidate = KnownFormMatch(
                form_id=form["form_id"],
                display_name=form.get("display_name", form["form_id"]),
                category=DocumentCategory(form.get("category", "other")),
                score=round(score, 3),
                matched_terms=matched_terms,
                unknown=score < self.settings.known_form_match_threshold,
            )
            if best is None or candidate.score > best.score:
                best = candidate
        if best is None or best.unknown:
            return KnownFormMatch(unknown=True, score=best.score if best else 0.0)
        return best
