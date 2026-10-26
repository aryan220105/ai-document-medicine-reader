import httpx
import pytest

from app.api.errors import AppError
from app.services.speech_service import SpeechService


def test_speech_is_unavailable_without_a_key(settings):
    settings.elevenlabs_api_key = ""
    with pytest.raises(AppError) as caught:
        SpeechService(settings).synthesize("Write your name.", "en")
    assert caught.value.status_code == 503


def test_speech_sends_the_guidance_sentence_and_the_language(settings, monkeypatch):
    settings.elevenlabs_api_key = "test-key"
    settings.elevenlabs_voice_id = "voice-1"
    settings.elevenlabs_model_id = "eleven_v3"
    captured: dict = {}

    class FakeResponse:
        status_code = 200
        content = b"ID3audio"

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)
    audio = SpeechService(settings).synthesize("اپنا پورا نام لکھیں۔", "ur")
    assert audio == b"ID3audio"
    assert captured["json"]["language_code"] == "ur"
    assert captured["json"]["model_id"] == "eleven_v3"
    assert captured["json"]["text"] == "اپنا پورا نام لکھیں۔"
    assert captured["headers"]["xi-api-key"] == "test-key"
    assert "voice-1" in captured["url"]


def test_speech_rejects_an_unsupported_language(settings):
    settings.elevenlabs_api_key = "test-key"
    with pytest.raises(AppError) as caught:
        SpeechService(settings).synthesize("Hello", "fr")
    assert caught.value.status_code == 400
