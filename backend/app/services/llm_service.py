from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.models.guidance import LLMGuidancePayload
from app.providers.llm.disabled import DisabledLLMProvider
from app.providers.llm.groq_provider import GroqProvider, LLMUnavailableError

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "field_guidance_system.txt"


class LLMService:
    def __init__(self, provider: GroqProvider | DisabledLLMProvider) -> None:
        self.provider = provider
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def available(self) -> bool:
        return self.provider.available()

    def interpret_field(self, user_prompt: str) -> LLMGuidancePayload | None:
        if not self.available():
            return None
        raw = self.provider.generate_sync(system_prompt=self.system_prompt, user_prompt=user_prompt)
        parsed = self._parse(raw)
        if parsed is not None:
            return parsed
        correction = (
            "The previous response was not valid JSON for the required schema. "
            "Return only the JSON object. Previous output:\n" + raw[:1200]
        )
        try:
            retry = self.provider.generate_sync(system_prompt=self.system_prompt, user_prompt=correction)
        except LLMUnavailableError:
            return None
        return self._parse(retry)

    def _parse(self, raw: str) -> LLMGuidancePayload | None:
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            payload = json.loads(raw[start : end + 1] if start >= 0 and end > start else raw)
            return LLMGuidancePayload.model_validate(payload)
        except (ValueError, ValidationError):
            logger.info("Discarded malformed LLM guidance payload")
            return None
