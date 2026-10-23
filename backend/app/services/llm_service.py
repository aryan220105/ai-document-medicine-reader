from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.models.common import Language
from app.models.guidance import LLMGuidancePayload, LLMMultilingualPayload
from app.providers.llm.disabled import DisabledLLMProvider
from app.providers.llm.groq_provider import GroqProvider, LLMUnavailableError
from app.utils.text_normalization import dominant_script

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "field_guidance_system.txt"

# A language's text is only accepted if it is actually written in that language's script.
# Models asked for Hindi often answer in romanised Hindi, which is useless to a reader who
# needs Devanagari, and worse than an honest gap because it looks like a translation.
EXPECTED_SCRIPT = {
    Language.ENGLISH: "latin",
    Language.HINDI: "devanagari",
    Language.KANNADA: "kannada",
    Language.URDU: "arabic",
}


class LLMService:
    def __init__(self, provider: GroqProvider | DisabledLLMProvider) -> None:
        self.provider = provider
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def available(self) -> bool:
        return self.provider.available()

    def interpret_field(self, user_prompt: str) -> LLMGuidancePayload | None:
        """Single-language reading, kept for the original guidance path."""
        payload = self.interpret_field_multilingual(user_prompt, [Language.ENGLISH])
        if payload is None:
            return None
        return payload.for_language(Language.ENGLISH)

    def interpret_field_multilingual(
        self, user_prompt: str, languages: list[Language]
    ) -> LLMMultilingualPayload | None:
        if not self.available():
            return None
        try:
            raw = self.provider.generate_sync(system_prompt=self.system_prompt, user_prompt=user_prompt)
        except LLMUnavailableError:
            return None
        parsed = self._parse(raw)
        if parsed is None:
            correction = (
                "The previous response was not valid JSON for the required schema. "
                "Return only the JSON object. Previous output:\n" + raw[:1200]
            )
            try:
                parsed = self._parse(self.provider.generate_sync(system_prompt=self.system_prompt, user_prompt=correction))
            except LLMUnavailableError:
                return None
        if parsed is None:
            return None
        return self._keep_native(parsed, languages)

    def _parse(self, raw: str) -> LLMMultilingualPayload | None:
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            payload = json.loads(raw[start : end + 1] if start >= 0 and end > start else raw)
        except (ValueError, TypeError):
            logger.info("Discarded malformed LLM guidance payload")
            return None
        payload = self._widen(payload)
        try:
            return LLMMultilingualPayload.model_validate(payload)
        except ValidationError:
            logger.info("Discarded LLM guidance payload that did not match the schema")
            return None

    @staticmethod
    def _widen(payload: object) -> dict:
        """Accept the older flat shape (plain strings) as English-only."""
        if not isinstance(payload, dict):
            return {}
        widened = dict(payload)
        for key in ("simple_label", "what_to_enter", "why_needed", "format_hint"):
            value = widened.get(key)
            if isinstance(value, str):
                widened[key] = {Language.ENGLISH.value: value}
            elif value is None:
                widened[key] = {}
        return widened

    def _keep_native(self, payload: LLMMultilingualPayload, languages: list[Language]) -> LLMMultilingualPayload | None:
        """Drop any language the model did not actually write in the right script."""
        kept: dict[str, str] = {}
        for language in languages:
            text = (payload.what_to_enter.get(language.value) or "").strip()
            if not text:
                continue
            if dominant_script(text) != EXPECTED_SCRIPT[language]:
                logger.info("Dropped LLM guidance for %s: wrong script", language.value)
                continue
            kept[language.value] = text
        if not kept:
            return None
        payload.what_to_enter = kept
        payload.simple_label = {key: value for key, value in payload.simple_label.items() if key in kept}
        payload.why_needed = {key: value for key, value in payload.why_needed.items() if key in kept}
        payload.format_hint = {key: value for key, value in payload.format_hint.items() if key in kept}
        return payload
