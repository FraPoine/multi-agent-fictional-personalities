from pathlib import Path
from typing import Mapping

from multi_agent_personalities.models import (
    GenerationMetadata,
    GenerationResult,
)


class MockProvider:
    """LLM provider that returns deterministic responses from local files."""

    def __init__(self, responses: Mapping[str, Path]) -> None:
        self._responses = dict(responses)

    def generate(
        self,
        prompt: str,
        *,
        task_name: str,
    ) -> GenerationResult:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        if task_name not in self._responses:
            raise ValueError(
                f"No mock response configured for task: {task_name}"
            )

        response_path = self._responses[task_name]

        if not response_path.is_file():
            raise FileNotFoundError(
                f"Mock response file not found: {response_path}"
            )

        response_text = response_path.read_text(encoding="utf-8")
        return GenerationResult(
            text=response_text,
            metadata=GenerationMetadata(
                provider="mock",
                model=None,
                usage=None,
                finish_reason="completed",
                request_id=None,
                latency_ms=None,
                retry_count=0,
            ),
        )
