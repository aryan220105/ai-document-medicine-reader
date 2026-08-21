from __future__ import annotations

import logging
from typing import Any

from openai import APIStatusError, NotFoundError, OpenAI, RateLimitError

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_MODELS = (
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
)


class LLMUnavailableError(RuntimeError):
    pass


class LLMRateLimitedError(RuntimeError):
    pass


class LLMModelMissingError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    """OpenAI-compatible chat client with API-key and model failover."""

    def __init__(
        self,
        api_keys: list[str],
        model: str,
        base_url: str | None = None,
        fallback_models: list[str] | None = None,
    ) -> None:
        self.api_keys = [key.strip() for key in api_keys if key and key.strip()]
        models: list[str] = []
        for item in [model, *(fallback_models or DEFAULT_FALLBACK_MODELS)]:
            value = (item or "").strip()
            if value and value not in models:
                models.append(value)
        self.models = models or ["openai/gpt-oss-20b"]
        self.model = self.models[0]
        self.base_url = (base_url or "").strip() or None
        self._index = 0
        self._model_index = 0

    def available(self) -> bool:
        return bool(self.api_keys)

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        return self.generate_sync(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )

    def generate_sync(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        if not self.api_keys:
            raise LLMUnavailableError(
                "LLM features require an API key. OCR and document extraction remain available."
            )

        last_rate_limit: Exception | None = None
        last_error: Exception | None = None
        key_count = len(self.api_keys)
        model_count = len(self.models)

        for model_offset in range(model_count):
            model = self.models[(self._model_index + model_offset) % model_count]
            for offset in range(key_count):
                index = (self._index + offset) % key_count
                key = self.api_keys[index]
                try:
                    text = self._complete(
                        api_key=key,
                        model=model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=temperature,
                    )
                    self._index = index
                    self._model_index = (self._model_index + model_offset) % model_count
                    self.model = model
                    if offset or model_offset:
                        logger.info("Using LLM model %s with key index %s", model, index)
                    return text
                except Exception as exc:
                    last_error = exc
                    if self._is_model_missing(exc):
                        logger.warning("LLM model %s is unavailable; trying the next model", model)
                        break
                    if self._is_rate_limit(exc):
                        last_rate_limit = exc
                        logger.warning(
                            "LLM rate limit on key index %s; trying next configured key",
                            index,
                        )
                        continue
                    if self._is_retryable(exc) and offset + 1 < key_count:
                        logger.warning(
                            "Retryable LLM error on key index %s: %s",
                            index,
                            type(exc).__name__,
                        )
                        continue
                    raise

        if last_rate_limit is not None:
            raise LLMRateLimitedError(
                "All configured LLM API keys are currently rate-limited. Please try again shortly."
            ) from last_rate_limit
        raise LLMUnavailableError(
            "The language model could not generate a response. The configured Groq model may no longer be available."
        ) from last_error

    def _complete(
        self,
        *,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        client = OpenAI(api_key=api_key, base_url=self.base_url)
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
        choice = response.choices[0].message.content or ""
        return choice.strip()

    @staticmethod
    def _is_model_missing(exc: Exception) -> bool:
        if isinstance(exc, NotFoundError):
            return True
        if isinstance(exc, APIStatusError) and exc.status_code == 404:
            return True
        text = str(exc).lower()
        return "model_not_found" in text or "does not exist" in text or "model_not_available" in text

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        if isinstance(exc, RateLimitError):
            return True
        if isinstance(exc, APIStatusError) and exc.status_code == 429:
            return True
        text = str(exc).lower()
        return "429" in text or "rate_limit" in text or "rate limit" in text or "too many requests" in text

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, APIStatusError) and exc.status_code in {500, 502, 503, 504}:
            return True
        text = str(exc).lower()
        return "temporarily" in text or "overloaded" in text
