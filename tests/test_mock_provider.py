from pathlib import Path

import pytest

from multi_agent_personalities.llm.mock_provider import MockProvider


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

    assert result == "Mock response"


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
            