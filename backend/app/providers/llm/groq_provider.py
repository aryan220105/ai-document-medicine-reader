from __future__ import annotations

import logging
from typing import Any

from openai import APIStatusError, NotFoundError, OpenAI, RateLimitError

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    pass


class LLMRateLimitedError(RuntimeError):
    pass


class GroqProvider:
    def __init__(
        self,
        api_keys: list[str],
        models: list[str],
        base_url: str,
        timeout_seconds: int = 30,
    ) -> None:
        self.api_keys = [key.strip() for key in api_keys if key and key.strip()]
        self.models = [model.strip() for model in models if model and model.strip()]
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self._index = 0
        self._model_index = 0

    def available(self) -> bool:
        return bool(self.api_keys) and bool(self.models)

    def generate_sync(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
        if not self.available():
            raise LLMUnavailableError(
                "External AI guidance is unavailable. Known-form and common-field help remain available."
            )
        last_rate: Exception | None = None
        last_error: Exception | None = None
        for model_offset in range(len(self.models)):
            model = self.models[(self._model_index + model_offset) % len(self.models)]
            for offset in range(len(self.api_keys)):
                index = (self._index + offset) % len(self.api_keys)
                try:
                    text = self._complete(self.api_keys[index], model, system_prompt, user_prompt, temperature)
                    self._index = index
                    self._model_index = (self._model_index + model_offset) % len(self.models)
                    return text
                except Exception as exc:
                    last_error = exc
                    if self._is_model_missing(exc):
                        break
                    if self._is_rate_limit(exc):
                        last_rate = exc
                        continue
                    if self._is_retryable(exc) and offset + 1 < len(self.api_keys):
                        continue
                    raise
        if last_rate is not None:
            raise LLMRateLimitedError("All configured Groq keys are rate-limited.") from last_rate
        raise LLMUnavailableError("The language model could not generate a response.") from last_error

    def _complete(self, api_key: str, model: str, system_prompt: str, user_prompt: str, temperature: float) -> str:
        client = OpenAI(api_key=api_key, base_url=self.base_url, timeout=self.timeout_seconds)
        kwargs: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:
            if self._is_model_missing(exc) or self._is_rate_limit(exc):
                raise
            kwargs.pop("response_format", None)
            response = client.chat.completions.create(**kwargs)
        return (response.choices[0].message.content or "").strip()

    @staticmethod
    def _is_model_missing(exc: Exception) -> bool:
        if isinstance(exc, NotFoundError):
            return True
        text = str(exc).lower()
        return "model_not_found" in text or "does not exist" in text

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        if isinstance(exc, RateLimitError):
            return True
        if isinstance(exc, APIStatusError) and exc.status_code == 429:
            return True
        return "429" in str(exc) or "rate_limit" in str(exc).lower()

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, APIStatusError) and exc.status_code in {500, 502, 503, 504}:
            return True
        return "overloaded" in str(exc).lower()
