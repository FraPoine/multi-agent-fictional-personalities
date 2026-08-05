from pathlib import Path

import pytest
from pydantic import ValidationError

from multi_agent_personalities.llm.mock_provider import MockProvider
from multi_agent_personalities.models import GenerationResult


def test_returns_response_from_file(tmp_path: Path) -> None:
    response_file = tmp_path / "response.txt"
    response_file.write_text("Mock response", encoding="utf-8")

    provider = MockProvider(
        {"persona_extraction": response_file}
    )

    result = provider.generate(
        "Extract the persona",
        task_name="persona_extraction",
    )

    assert isinstance(result, GenerationResult)
    assert result.text == "Mock response"
    assert result.metadata.provider == "mock"
    assert result.metadata.model is None
    assert result.metadata.usage is None
    assert result.metadata.finish_reason == "completed"
    assert result.metadata.request_id is None
    assert result.metadata.latency_ms is None
    assert result.metadata.retry_count == 0


def test_preserves_file_text_and_returns_deterministic_results(
    tmp_path: Path,
) -> None:
    response_file = tmp_path / "response.txt"
    response_file.write_text("  Mock response\n", encoding="utf-8")
    provider = MockProvider({"agent_reply": response_file})

    first = provider.generate("Prompt", task_name="agent_reply")
    second = provider.generate("Prompt", task_name="agent_reply")

    assert first.text == "  Mock response\n"
    assert first == second
    assert first.metadata == second.metadata
    assert first.metadata.usage is None
    assert first.metadata.request_id is None
    assert first.metadata.latency_ms is None
    assert first.metadata.retry_count == 0


def test_rejects_empty_prompt(tmp_path: Path) -> None:
    response_file = tmp_path / "response.txt"
    response_file.write_text("Mock response", encoding="utf-8")

    provider = MockProvider(
        {"persona_extraction": response_file}
    )

    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        provider.generate(
            "   ",
            task_name="persona_extraction",
        )


def test_rejects_unknown_task(tmp_path: Path) -> None:
    response_file = tmp_path / "response.txt"
    response_file.write_text("Mock response", encoding="utf-8")

    provider = MockProvider(
        {"persona_extraction": response_file}
    )

    with pytest.raises(
        ValueError,
        match="No mock response configured",
    ):
        provider.generate(
            "Generate a reply",
            task_name="agent_reply",
        )


def test_rejects_missing_response_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.txt"

    provider = MockProvider(
        {"persona_extraction": missing_file}
    )

    with pytest.raises(
        FileNotFoundError,
        match="Mock response file not found",
    ):
        provider.generate(
            "Extract the persona",
            task_name="persona_extraction",
        )


@pytest.mark.parametrize("content", ["", " \n\t"])
def test_rejects_empty_response_content(tmp_path: Path, content: str) -> None:
    response_file = tmp_path / "response.txt"
    response_file.write_text(content, encoding="utf-8")
    provider = MockProvider({"agent_reply": response_file})

    with pytest.raises(ValidationError, match="text must not be empty"):
        provider.generate("Prompt", task_name="agent_reply")


def test_read_error_propagates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response_file = tmp_path / "response.txt"
    response_file.write_text("Mock response", encoding="utf-8")
    provider = MockProvider({"agent_reply": response_file})

    def fail_read_text(path: Path, *, encoding: str) -> str:
        raise OSError("simulated read failure")

    monkeypatch.setattr(Path, "read_text", fail_read_text)
    with pytest.raises(OSError, match="simulated read failure"):
        provider.generate("Prompt", task_name="agent_reply")
