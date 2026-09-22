from __future__ import annotations

from app.models.common import FieldType, GuidanceSource, Language
from app.models.fields import DetectedField
from app.models.guidance import AskRequest, AskResponse, FieldGuidance, GuidanceRequest
from app.models.ocr import OCRResult
from app.repositories.form_knowledge_repository import FormKnowledgeRepository
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService
from app.services.translation_service import TranslationService
from app.utils.text_normalization import fold


class GuidanceService:
    def __init__(
        self,
        knowledge: FormKnowledgeRepository,
        retrieval: RetrievalService,
        llm: LLMService,
        translation: TranslationService,
        common_threshold: float,
        retrieval_threshold: float,
    ) -> None:
        self.knowledge = knowledge
        self.retrieval = retrieval
        self.llm = llm
        self.translation = translation
        self.common_threshold = common_threshold
        self.retrieval_threshold = retrieval_threshold

    def for_field(
        self,
        field: DetectedField,
        request: GuidanceRequest,
        form_id: str | None,
        ocr_pages: list[OCRResult],
    ) -> FieldGuidance:
        known = self._known(field, request.language, form_id)
        if known:
            return known
        common = self._common(field, request.language)
        if common:
            return common
        retrieved = self._retrieved(field, request.language, form_id)
        if retrieved:
            return retrieved
        if request.allow_external_ai:
            ai = self._llm(field, request, ocr_pages)
            if ai:
                return ai
        return self._unavailable(field, request.language)

    def ask(
        self,
        field: DetectedField,
        request: AskRequest,
        form_id: str | None,
        ocr_pages: list[OCRResult],
    ) -> AskResponse:
        question = fold(request.question)
        if any(term in question for term in ("where", "location", "highlight")):
            return AskResponse(
                answer="This is the printed region associated with the selected field.",
                source=GuidanceSource.FORM_TEXT,
                highlights=[field.input_box, *field.label_boxes],
                refused=False,
            )
        if any(term in question for term in ("fill this", "my name", "what should i write as my", "enter my")):
            return AskResponse(
                answer="FormSathi will not invent the value you should write. Use the official instructions and your own records.",
                source=GuidanceSource.UNAVAILABLE,
                highlights=[field.input_box],
                refused=True,
            )
        guidance = self.for_field(
            field,
            GuidanceRequest(field_id=field.id, language=request.language, allow_external_ai=request.allow_external_ai),
            form_id,
            ocr_pages,
        )
        return AskResponse(
            answer=guidance.what_to_enter,
            source=guidance.source,
            highlights=[field.input_box, *field.label_boxes],
            llm_used=guidance.source == GuidanceSource.GENERAL_AI,
            refused=False,
        )

    def prompt_contains_user_answer(self, prompt: str, answers: list[str]) -> bool:
        folded = fold(prompt)
        return any(value and fold(value) in folded for value in answers if len(value.strip()) >= 3)

    def _known(self, field: DetectedField, language: Language, form_id: str | None) -> FieldGuidance | None:
        if not form_id:
            return None
        match = self.knowledge.find_field(form_id, [field.label, field.id, field.known_field_id or ""], language)
        if not match:
            return None
        item = match["field"]
        return FieldGuidance(
            field_id=field.id,
            language=language,
            simple_label=field.label or item["field_id"],
            what_to_enter=item["what_to_enter"][language.value],
            why_needed=item.get("why_needed", {}).get(language.value),
            example=item.get("example"),
            format_hint=item.get("validation", {}).get("format"),
            source=GuidanceSource.KNOWN_FORM,
            source_reference=item.get("source_reference"),
            confidence=0.93,
            requires_verification=False,
            highlights=[field.input_box, *field.label_boxes],
        )

    def _common(self, field: DetectedField, language: Language) -> FieldGuidance | None:
        label = fold(field.label)
        best: tuple[float, dict] | None = None
        for item in self.knowledge.common_fields:
            aliases = [fold(alias) for alias in item.get("aliases", [])]
            score = 1.0 if any(alias and (alias in label or label in alias) for alias in aliases) else 0.0
            if field.field_type == FieldType.DATE and item.get("type") == "date":
                score = max(score, 0.7)
            if score >= self.common_threshold and (best is None or score > best[0]):
                best = (score, item)
        if best is None:
            return None
        item = best[1]
        return FieldGuidance(
            field_id=field.id,
            language=language,
            simple_label=item.get("simple_label", {}).get(language.value, field.label),
            what_to_enter=item["what_to_enter"][language.value],
            why_needed=item.get("why_needed", {}).get(language.value),
            example=item.get("example"),
            format_hint=item.get("format_hint"),
            source=GuidanceSource.COMMON_DICTIONARY,
            source_reference=item.get("id"),
            confidence=0.86 if best[0] >= 1 else 0.72,
            requires_verification=best[0] < 1,
            highlights=[field.input_box, *field.label_boxes],
        )

    def _retrieved(self, field: DetectedField, language: Language, form_id: str | None) -> FieldGuidance | None:
        hits = self.retrieval.retrieve(field.label or field.id, language, form_id)
        if not hits:
            return None
        top = hits[0]
        if top["score"] < self.retrieval_threshold:
            return None
        metadata = top["metadata"]
        return FieldGuidance(
            field_id=field.id,
            language=language,
            simple_label=field.label or metadata.get("field_id", "Field"),
            what_to_enter=metadata.get("what_to_enter") or self.translation.unavailable_message(language),
            why_needed=metadata.get("why_needed") or None,
            example=metadata.get("example"),
            source=GuidanceSource.KNOWN_FORM,
            source_reference=metadata.get("source_reference"),
            confidence=min(0.84, 0.5 + top["score"] / 2),
            requires_verification=True,
            highlights=[field.input_box, *field.label_boxes],
        )

    def _llm(self, field: DetectedField, request: GuidanceRequest, ocr_pages: list[OCRResult]) -> FieldGuidance | None:
        nearby = self._nearby_text(field, ocr_pages)
        prompt = (
            f"Language: {request.language.value}\n"
            f"Category: {request.category.value if getattr(request, 'category', None) else 'other'}\n"
            f"Printed label: {field.label}\n"
            f"Detected type: {field.field_type.value}\n"
            f"Nearby printed text: {nearby}\n"
            "Do not invent personal answers. Return JSON only."
        )
        payload = self.llm.interpret_field(prompt)
        if payload is None:
            return None
        return FieldGuidance(
            field_id=field.id,
            language=request.language,
            simple_label=payload.simple_label,
            what_to_enter=payload.what_to_enter,
            why_needed=payload.why_needed,
            example=payload.example,
            format_hint=payload.format_hint,
            source=GuidanceSource.GENERAL_AI,
            source_reference="groq",
            confidence=0.58,
            requires_verification=True,
            highlights=[field.input_box, *field.label_boxes],
        )

    def _unavailable(self, field: DetectedField, language: Language) -> FieldGuidance:
        return FieldGuidance(
            field_id=field.id,
            language=language,
            simple_label=field.label or "Field",
            what_to_enter=self.translation.unavailable_message(language),
            source=GuidanceSource.UNAVAILABLE,
            confidence=0.2,
            requires_verification=True,
            highlights=[field.input_box, *field.label_boxes],
        )

    def _nearby_text(self, field: DetectedField, ocr_pages: list[OCRResult]) -> str:
        words = []
        for page in ocr_pages:
            if page.page_index != field.page_index:
                continue
            for word in page.words:
                if abs(word.box.y - field.input_box.y) < 0.08:
                    words.append(word)
        words.sort(key=lambda item: (item.box.y, item.box.x))
        return " ".join(word.text for word in words[:40])[:400]
