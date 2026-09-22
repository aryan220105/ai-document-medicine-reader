from typing import Protocol


class LLMProvider(Protocol):
    def available(self) -> bool:
        ...

    def generate_sync(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
        ...
