"""Read guidance aloud with ElevenLabs.

Only the explanation text is sent. Answers, page images, and uploaded files never are.
Eleven v3 is the model that speaks Kannada and Urdu; multilingual v2 does not.
"""

from __future__ import annotations

import logging
import re
import time

import httpx

from app.api.errors import AppError
from app.config import Settings
from app.models.common import Language

logger = logging.getLogger(__name__)

SUPPORTED = {language.value for language in Language}
MAX_CHARS = 1200
# A shared demo key should not be drained by a loop. Guidance is one short paragraph.
SPEECH_LIMIT = 40
SPEECH_WINDOW_SECONDS = 600

_WHITESPACE = re.compile(r"\s+")


class SpeechService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._hits: list[float] = []

    @property
    def configured(self) -> bool:
        return self.settings.speech_configured

    def synthesize(self, text: str, language: str) -> bytes:
        if not self.configured:
            raise AppError(
                503,
                "speech_unconfigured",
                "Read-aloud is not configured. Add ELEVENLABS_API_KEY to the server environment.",
            )
        code = (language or "").strip().lower()
        if code not in SUPPORTED:
            raise AppError(400, "unsupported_language", "Read-aloud supports English, Hindi, Kannada, and Urdu.")
        spoken = _WHITESPACE.sub(" ", (text or "").strip())
        if not spoken:
            raise AppError(400, "empty_speech", "There is no guidance to read aloud.")
        if len(spoken) > MAX_CHARS:
            spoken = spoken[:MAX_CHARS].rsplit(" ", 1)[0].strip() or spoken[:MAX_CHARS]

        self._limit()
        payload = {
            "text": spoken,
            "model_id": self.settings.elevenlabs_model_id.strip() or "eleven_v3",
            "language_code": code,
        }
        url = (
            "https://api.elevenlabs.io/v1/text-to-speech/"
            f"{self.settings.elevenlabs_voice_id.strip()}"
        )
        headers = {
            "xi-api-key": self.settings.elevenlabs_api_key.strip(),
            "accept": "audio/mpeg",
            "content-type": "application/json",
        }
        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.settings.elevenlabs_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            logger.warning("ElevenLabs request failed: %s", type(exc).__name__)
            raise AppError(502, "speech_unavailable", "Read-aloud could not be reached. The text below is complete.") from exc

        if response.status_code >= 400:
            logger.warning("ElevenLabs returned %s", response.status_code)
            raise AppError(502, "speech_failed", "Read-aloud could not be generated. The text below is complete.")
        audio = response.content
        if not audio:
            raise AppError(502, "speech_empty", "Read-aloud returned no audio. The text below is complete.")
        return audio

    def _limit(self) -> None:
        now = time.monotonic()
        self._hits = [hit for hit in self._hits if now - hit < SPEECH_WINDOW_SECONDS]
        if len(self._hits) >= SPEECH_LIMIT:
            raise AppError(429, "speech_rate_limited", "Too many read-aloud requests. Wait a moment and try again.")
        self._hits.append(now)
