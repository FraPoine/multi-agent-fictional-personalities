from typing import Protocol


class LLMProvider(Protocol):
    """Common interface for all LLM providers."""

    def generate(
        self,
        prompt: str,
        *,
        task_name: str,
    ) -> str:
        """Generate and return a textual response."""
        ...
