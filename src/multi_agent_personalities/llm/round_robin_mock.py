"""Deterministic local provider for multi-participant mock conversations."""

from collections.abc import Sequence


class RoundRobinMockProvider:
    """Return configured response fixtures cyclically in participant order."""

    def __init__(self, responses: Sequence[str]) -> None:
        if not responses:
            raise ValueError("at least one mock response is required")
        if any(not isinstance(response, str) or not response.strip()
               for response in responses):
            raise ValueError("mock responses must be non-empty strings")
        self._responses = tuple(responses)
        self._call_count = 0

    def generate(self, prompt: str, *, task_name: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        if task_name != "agent_reply":
            raise ValueError(f"Unsupported mock task: {task_name}")
        response = self._responses[self._call_count % len(self._responses)]
        self._call_count += 1
        return response
