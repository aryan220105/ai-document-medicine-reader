from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.config import Settings
from app.models.chat import LLMStructuredOutput
from app.models.common import DocumentType, Language
from app.providers.llm.openai_compatible import (
    LLMUnavailableError,
    OpenAICompatibleProvider,
)
from app.utils.text import snippet

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class LLMService:
    def __init__(self, settings: Settings, provider: OpenAICompatibleProvider | None = None) -> None:
        self.settings = settings
        self.provider = provider or OpenAICompatibleProvider(
            api_keys=settings.llm_api_keys(),
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            fallback_models=settings.llm_fallback_models(),
        )
        self.system_prompt = (PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8")
        self.medicine_prompt = (PROMPTS_DIR / "medicine_prompt.txt").read_text(encoding="utf-8")

    @property
    def configured(self) -> bool:
        return self.provider.available()

    async def generate_answer(
        self,
        *,
        question: str,
        document_context: str,
        knowledge_context: str,
        language: Language,
        easy_read: bool,
        document_type: DocumentType,
        ocr_confidence: float,
    ) -> LLMStructuredOutput:
        if not self.configured:
            raise LLMUnavailableError(
                "LLM features require an API key. OCR and document extraction remain available."
            )
        system = self.system_prompt
        if document_type == DocumentType.MEDICINE_LABEL:
            system = f"{system}\n\n{self.medicine_prompt}"
        language_name = {
            Language.ENGLISH: "English",
            Language.HINDI: "Hindi",
            Language.KANNADA: "Kannada",
        }[language]
        style = "Use short sentences and very simple words." if easy_read else "Be clear and concise."
        user_prompt = (
            f"ANSWER LANGUAGE: {language_name}\n"
            f"STYLE: {style}\n"
            f"DOCUMENT TYPE: {document_type.value}\n"
            f"OCR AVERAGE CONFIDENCE: {ocr_confidence:.1f}\n\n"
            f"DOCUMENT CONTEXT:\n{document_context or '(no document text retrieved)'}\n\n"
            f"SUPPLEMENTAL KNOWLEDGE:\n{knowledge_context or '(none)'}\n\n"
            f"USER QUESTION:\n{question}\n"
        )
        raw = await asyncio.to_thread(
            self.provider.generate_sync,
            system_prompt=system,
            user_prompt=user_prompt,
        )
        parsed = self._parse(raw)
        if parsed is not None:
            return parsed
        raw_retry = await asyncio.to_thread(
            self.provider.generate_sync,
            system_prompt=system + "\nReturn JSON only. Do not wrap in markdown.",
            user_prompt=user_prompt,
        )
        parsed = self._parse(raw_retry)
        if parsed is not None:
            return parsed
        return LLMStructuredOutput(
            answer=self._plain_fallback(raw_retry or raw),
            confidence=0.4,
        )

    def _parse(self, raw: str) -> LLMStructuredOutput | None:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            data = json.loads(text)
            return LLMStructuredOutput.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return LLMStructuredOutput.model_validate(json.loads(text[start : end + 1]))
                except (json.JSONDecodeError, ValidationError):
                    return None
            return None

    @staticmethod
    def _plain_fallback(raw: str) -> str:
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        return snippet(cleaned, 600) or "I could not generate a reliable explanation for this question."
