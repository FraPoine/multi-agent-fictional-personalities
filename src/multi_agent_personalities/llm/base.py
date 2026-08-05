from typing import Protocol

from multi_agent_personalities.models import GenerationResult


class LLMProvider(Protocol):
    """Common interface for all LLM providers."""

    def generate(
        self,
        prompt: str,
        *,
        task_name: str,
    ) -> GenerationResult:
        """Generate and return one validated successful result."""
        ...
