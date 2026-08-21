from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        ...
