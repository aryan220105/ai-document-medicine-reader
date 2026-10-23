from __future__ import annotations

import logging
import time
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
        attempt_budget: float = 2.5,
    ) -> None:
        self.api_keys = [key.strip() for key in api_keys if key and key.strip()]
        self.models = [model.strip() for model in models if model and model.strip()]
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        # How many request-timeouts the whole failover matrix may consume before giving
        # up, so a hanging provider degrades quickly instead of stalling an upload.
        self.attempt_budget = max(1.0, attempt_budget)
        self._index = 0
        self._model_index = 0

    def available(self) -> bool:
        return bool(self.api_keys) and bool(self.models)

    def generate_with_model(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        """One call against a named model, outside the usual failover rotation.

        Used for Groq's web-search ("compound") models, which are a different model
        family from the ones configured for field work and are not interchangeable with
        them: falling back from a search model to a plain one would silently answer from
        the model's own memory instead of from a search, which is exactly the kind of
        invented background this must not produce. So there is no failover here -- it
        works or the caller does without it.
        """
        if not self.api_keys or not model:
            raise LLMUnavailableError("No web-search model is configured.")
        return self._complete(self.api_keys[self._index % len(self.api_keys)], model, system_prompt, user_prompt, temperature)

    def generate_sync(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> str:
        if not self.available():
            raise LLMUnavailableError(
                "External AI guidance is unavailable. Known-form and common-field help remain available."
            )
        # A deadline across the whole failover matrix, not just per request. With two
        # keys, two models, and a caller that retries once, a provider that hangs rather
        # than refusing can otherwise occupy a request for eight full timeouts; multiplied
        # by the batches in one upload that is the better part of an hour, during which
        # the page never finishes and the circuit breaker never gets a chance to trip.
        deadline = time.monotonic() + max(self.timeout_seconds, 1) * self.attempt_budget
        last_rate: Exception | None = None
        last_error: Exception | None = None
        for model_offset in range(len(self.models)):
            model = self.models[(self._model_index + model_offset) % len(self.models)]
            for offset in range(len(self.api_keys)):
                if time.monotonic() >= deadline:
                    logger.warning("Giving up on the language model: overall deadline reached")
                    raise LLMUnavailableError("The language model did not respond in time.") from last_error
                index = (self._index + offset) % len(self.api_keys)
                try:
                    text = self._complete(
                        self.api_keys[index], model, system_prompt, user_prompt, temperature, max_tokens
                    )
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

    def _complete(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int | None = None,
    ) -> str:
        # max_retries=0 because this class already retries: across keys, then across
        # models, under an overall deadline. Leaving the SDK's own retries on nests one
        # retry loop inside another, so a single unreachable host becomes a dozen
        # back-off waits. Measured during a real DNS outage: 256 seconds to fall back to
        # the offline path, where it should be near-instant.
        client = OpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            max_retries=0,
        )
        kwargs: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        if max_tokens:
            # Callers should think twice before setting this. These models reason before
            # answering and the reasoning is charged against the same budget, so a limit
            # that looks generous can consume the whole allowance and return an empty
            # message rather than a shorter one. Batching controls reply length instead.
            kwargs["max_tokens"] = int(max_tokens)
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:
            if self._is_model_missing(exc) or self._is_rate_limit(exc):
                raise
            kwargs.pop("response_format", None)
            response = client.chat.completions.create(**kwargs)
        text = self._content(response)
        if text:
            return text

        # An empty completion, with no error raised. These reasoning models do this
        # intermittently when JSON mode is combined with a long prompt: the reasoning is
        # produced and the visible message comes back blank. It is not a transport
        # failure, so nothing above notices, and the caller sees unparseable output.
        # Asking again without the JSON-mode constraint reliably produces the object --
        # the schema is in the system prompt anyway, and the caller extracts the object
        # from the reply either way.
        if "response_format" in kwargs:
            logger.info("Empty completion from %s; retrying without JSON mode", model)
            kwargs.pop("response_format", None)
            text = self._content(client.chat.completions.create(**kwargs))
        return text

    @staticmethod
    def _content(response: Any) -> str:
        try:
            return (response.choices[0].message.content or "").strip()
        except (AttributeError, IndexError):
            return ""

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
