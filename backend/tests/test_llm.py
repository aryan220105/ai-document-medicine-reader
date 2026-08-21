from app.providers.llm.openai_compatible import (
    LLMRateLimitedError,
    OpenAICompatibleProvider,
)


class FakeRateLimit(Exception):
    def __str__(self) -> str:
        return "Error code: 429 - rate_limit_exceeded"


def test_llm_disabled_without_keys() -> None:
    provider = OpenAICompatibleProvider(api_keys=[], model="llama-3.3-70b-versatile")
    assert provider.available() is False


def test_failover_to_second_key(monkeypatch) -> None:
    provider = OpenAICompatibleProvider(
        api_keys=["key-one", "key-two"],
        model="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
    )
    calls: list[str] = []

    def fake_complete(self, api_key: str, model: str, system_prompt: str, user_prompt: str, temperature: float) -> str:
        calls.append(api_key)
        if api_key == "key-one":
            raise FakeRateLimit()
        return '{"answer":"ok","document_evidence":[],"supplemental_evidence":[],"highlight_phrase":null,"confidence":0.9}'

    monkeypatch.setattr(OpenAICompatibleProvider, "_complete", fake_complete)
    result = provider.generate_sync(system_prompt="s", user_prompt="q")
    assert "ok" in result
    assert calls == ["key-one", "key-two"]
    assert provider._index == 1


def test_all_keys_rate_limited(monkeypatch) -> None:
    provider = OpenAICompatibleProvider(api_keys=["a", "b"], model="x")

    def always_limit(self, **kwargs):
        raise FakeRateLimit()

    monkeypatch.setattr(OpenAICompatibleProvider, "_complete", always_limit)
    try:
        provider.generate_sync(system_prompt="s", user_prompt="q")
        raise AssertionError("should have failed")
    except LLMRateLimitedError:
        pass


class FakeMissingModel(Exception):
    def __str__(self) -> str:
        return "Error code: 404 - model_not_found does not exist"


def test_failover_to_next_model(monkeypatch) -> None:
    provider = OpenAICompatibleProvider(
        api_keys=["only-key"],
        model="missing-model",
        fallback_models=["working-model"],
    )
    used: list[str] = []

    def fake_complete(self, api_key: str, model: str, system_prompt: str, user_prompt: str, temperature: float) -> str:
        used.append(model)
        if model == "missing-model":
            raise FakeMissingModel()
        return '{"answer":"ok"}'

    monkeypatch.setattr(OpenAICompatibleProvider, "_complete", fake_complete)
    result = provider.generate_sync(system_prompt="s", user_prompt="q")
    assert "ok" in result
    assert used == ["missing-model", "working-model"]
