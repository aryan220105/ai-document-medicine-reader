from __future__ import annotations

import logging

from fastapi import HTTPException

from app.models.chat import ChatRequest, ChatResponse, QuestionIntent
from app.models.common import DocumentType, Language
from app.models.document import DocumentRecord
from app.providers.llm.openai_compatible import LLMRateLimitedError, LLMUnavailableError
from app.services.answer_templates import (
    FIELD_ANSWERS,
    LLM_UNAVAILABLE,
    MISSING_TRANSLATIONS,
    field_by_type,
    simple_explanation,
)
from app.services.document_service import DocumentService
from app.services.highlight_service import HighlightService
from app.services.intent_service import IntentService
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.utils.text import snippet

logger = logging.getLogger(__name__)

KNOWLEDGE_INTENTS = {
    QuestionIntent.FOOD_INTERACTION,
    QuestionIntent.SIDE_EFFECTS,
    QuestionIntent.GENERAL_QUESTION,
    QuestionIntent.EXPLAIN_SIMPLY,
    QuestionIntent.SUMMARIZE,
}


class ChatService:
    def __init__(
        self,
        document_service: DocumentService,
        intent_service: IntentService,
        highlight_service: HighlightService,
        rag_service: RAGService,
        llm_service: LLMService,
    ) -> None:
        self.document_service = document_service
        self.intent_service = intent_service
        self.highlight_service = highlight_service
        self.rag_service = rag_service
        self.llm_service = llm_service

    async def ask(self, document_id: str, request: ChatRequest) -> ChatResponse:
        record = self.document_service.get(document_id)
        if record.ocr is None:
            raise HTTPException(
                status_code=409,
                detail="This document is still processing. Please wait until it is ready.",
            )
        intent, wants_location = self.intent_service.detect(request.question)
        combined = self._combined_deterministic(record, request.question, request.language)
        if combined is not None:
            return combined
        deterministic = self._deterministic(record, intent, request.language, wants_location)
        if deterministic is not None:
            return deterministic

        if intent in {QuestionIntent.EXPLAIN_SIMPLY, QuestionIntent.SUMMARIZE} and not self.llm_service.configured:
            answer = simple_explanation(record.fields, record.effective_type, request.language)
            highlights = self.highlight_service.find_highlights(
                record.ocr, intent, answer, record.fields, force=wants_location
            )
            return ChatResponse(
                answer=answer,
                document_sources=[snippet(record.ocr.full_text, 220)],
                highlights=highlights,
                confidence=0.7,
                intent=intent,
            )

        if not self.llm_service.configured:
            if intent in FIELD_ANSWERS:
                missing = FIELD_ANSWERS[intent]["missing_en"]
                if request.language != Language.ENGLISH:
                    missing = MISSING_TRANSLATIONS[request.language]
                return ChatResponse(
                    answer=str(missing),
                    confidence=0.2,
                    intent=intent,
                )
            return ChatResponse(
                answer=LLM_UNAVAILABLE[request.language],
                llm_unavailable=True,
                intent=intent,
            )

        document_hits = self.rag_service.retrieve_document(request.question, document_id)
        knowledge_hits = []
        if intent in KNOWLEDGE_INTENTS or record.effective_type == DocumentType.MEDICINE_LABEL:
            knowledge_hits = self.rag_service.retrieve_knowledge(request.question)
        document_context = "\n".join(hit.text for hit in document_hits) or record.ocr.full_text
        knowledge_context = "\n".join(hit.text for hit in knowledge_hits)
        try:
            structured = await self.llm_service.generate_answer(
                question=request.question,
                document_context=document_context,
                knowledge_context=knowledge_context,
                language=request.language,
                easy_read=request.easy_read,
                document_type=record.effective_type,
                ocr_confidence=record.ocr.average_confidence,
            )
        except LLMRateLimitedError as exc:
            return ChatResponse(
                answer=str(exc),
                llm_unavailable=True,
                intent=intent,
            )
        except LLMUnavailableError as exc:
            if intent in {QuestionIntent.EXPLAIN_SIMPLY, QuestionIntent.SUMMARIZE}:
                answer = simple_explanation(record.fields, record.effective_type, request.language)
                return ChatResponse(
                    answer=answer,
                    document_sources=[snippet(record.ocr.full_text, 220)],
                    confidence=0.7,
                    intent=intent,
                )
            return ChatResponse(
                answer=str(exc),
                llm_unavailable=True,
                intent=intent,
            )
        except Exception:
            logger.exception("LLM generation failed for document_id=%s", document_id)
            if intent in {QuestionIntent.EXPLAIN_SIMPLY, QuestionIntent.SUMMARIZE}:
                answer = simple_explanation(record.fields, record.effective_type, request.language)
                return ChatResponse(
                    answer=answer,
                    document_sources=[snippet(record.ocr.full_text, 220)],
                    confidence=0.7,
                    intent=intent,
                )
            return ChatResponse(
                answer=(
                    "AI explanation is temporarily unavailable. "
                    "You can still use the extracted text and detected fields."
                ),
                llm_unavailable=True,
                intent=intent,
            )

        highlights = self.highlight_service.find_highlights(
            record.ocr,
            intent,
            structured.answer,
            record.fields,
            highlight_phrase=structured.highlight_phrase,
            force=wants_location,
        )
        return ChatResponse(
            answer=structured.answer,
            document_sources=structured.document_evidence or [hit.text for hit in document_hits[:3]],
            knowledge_sources=structured.supplemental_evidence or [hit.source for hit in knowledge_hits[:3]],
            highlights=highlights,
            confidence=structured.confidence,
            intent=intent,
            llm_used=True,
        )

    def _deterministic(
        self,
        record: DocumentRecord,
        intent: QuestionIntent,
        language: Language,
        wants_location: bool,
    ) -> ChatResponse | None:
        if intent not in FIELD_ANSWERS:
            if wants_location:
                return self._location_from_fields(record, language)
            return None
        spec = FIELD_ANSWERS[intent]
        field = field_by_type(record.fields, str(spec["type"]))
        if field is None:
            if not self.llm_service.configured:
                missing = str(spec["missing_en"])
                if language != Language.ENGLISH:
                    missing = MISSING_TRANSLATIONS[language]
                return ChatResponse(answer=missing, intent=intent, confidence=0.2)
            return None
        template = spec.get(language) or spec[Language.ENGLISH]
        answer = str(template).format(value=field.value)
        if field.uncertain:
            answer = f"{answer} This reading may be uncertain because the OCR confidence is only medium or low."
        highlights = field.bounding_boxes
        if not highlights and record.ocr is not None:
            highlights = self.highlight_service.find_highlights(
                record.ocr, intent, field.value, record.fields, highlight_phrase=field.value, force=True
            )
        return ChatResponse(
            answer=answer,
            document_sources=[field.value],
            highlights=highlights,
            confidence=field.confidence,
            intent=intent,
        )

    def _combined_deterministic(
        self,
        record: DocumentRecord,
        question: str,
        language: Language,
    ) -> ChatResponse | None:
        text = question.lower()
        wants_amount = any(token in text for token in ("how much", "pay", "amount"))
        wants_due = any(token in text for token in ("due date", "deadline", "pay by"))
        if not (wants_amount and wants_due):
            return None
        amount = field_by_type(record.fields, "amount")
        due = field_by_type(record.fields, "due_date")
        if amount is None or due is None:
            return None
        amount_text = str(FIELD_ANSWERS[QuestionIntent.FIND_AMOUNT].get(language) or FIELD_ANSWERS[QuestionIntent.FIND_AMOUNT][Language.ENGLISH]).format(value=amount.value)
        due_text = str(FIELD_ANSWERS[QuestionIntent.FIND_DUE_DATE].get(language) or FIELD_ANSWERS[QuestionIntent.FIND_DUE_DATE][Language.ENGLISH]).format(value=due.value)
        return ChatResponse(
            answer=f"{amount_text} {due_text}",
            document_sources=[amount.value, due.value],
            highlights=[*amount.bounding_boxes, *due.bounding_boxes],
            confidence=min(amount.confidence, due.confidence),
            intent=QuestionIntent.FIND_AMOUNT,
        )

    def _location_from_fields(self, record: DocumentRecord, language: Language) -> ChatResponse | None:
        if not record.fields:
            return None
        field = max(record.fields, key=lambda item: item.confidence)
        prefix = {
            Language.ENGLISH: "I highlighted this printed value",
            Language.HINDI: "मैंने यह छपा हुआ मान चिह्नित किया है",
            Language.KANNADA: "ಮುದ್ರಿತ ಮೌಲ್ಯವನ್ನು ಗುರುತಿಸಲಾಗಿದೆ",
        }[language]
        return ChatResponse(
            answer=f"{prefix}: {field.value}.",
            document_sources=[field.value],
            highlights=field.bounding_boxes,
            confidence=field.confidence,
            intent=QuestionIntent.VISUAL_LOCATION,
        )
