from pathlib import Path
from typing import Mapping


class MockProvider:
    """LLM provider that returns deterministic responses from local files."""

    def __init__(self, responses: Mapping[str, Path]) -> None:
        self._responses = dict(responses)

    def generate(
        self,
        prompt: str,
        *,
        task_name: str,
    ) -> str:
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

        return response_path.read_text(encoding="utf-8")
