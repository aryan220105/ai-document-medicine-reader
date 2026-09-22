from app.providers.llm.groq_provider import LLMUnavailableError


class DisabledLLMProvider:
    def available(self) -> bool:
        return False

    def generate_sync(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
        raise LLMUnavailableError(
            "External AI guidance is turned off. Known-form and common-field help remain available."
        )
