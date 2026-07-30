"""End-to-end test for the deterministic Sprint 2 mock pipeline."""

import json
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

import multi_agent_personalities.pipeline as pipeline_module
from multi_agent_personalities.llm import MockProvider
from multi_agent_personalities.models.persona import Persona
from multi_agent_personalities.pipeline import (
    default_pipeline_paths,
    run_pipeline,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIRECTORY = PROJECT_ROOT / "tests" / "fixtures"


@pytest.mark.parametrize(
    ("character", "character_id", "display_name"),
    [
        ("poirot", "hercule_poirot", "Hercule Poirot"),
        ("sherlock", "sherlock_holmes", "Sherlock Holmes"),
    ],
)
def test_mock_pipeline_runs_end_to_end_without_openai(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    character: str,
    character_id: str,
    display_name: str,
) -> None:
    """Exercise the public pipeline with only deterministic local responses."""

    provider_tasks: list[str] = []

    class TrackingMockProvider(MockProvider):
        def generate(self, prompt: str, *, task_name: str) -> str:
            provider_tasks.append(task_name)
            return super().generate(prompt, task_name=task_name)

    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("The mock pipeline attempted network access")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(
        pipeline_module,
        "MockProvider",
        TrackingMockProvider,
    )
    monkeypatch.chdir(tmp_path)

    user_message = "Which clue should we examine first?"
    run_directory = run_pipeline(
        character=character,
        provider_name="mock",
        user_message=user_message,
        output_root=tmp_path / "generated",
        paths=default_pipeline_paths(PROJECT_ROOT, character),
        timestamp=datetime(
            2026,
            7,
            28,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert provider_tasks == ["persona_extraction", "agent_reply"]
    assert run_directory.is_relative_to(tmp_path)
    assert {path.name for path in run_directory.iterdir()} == {
        "persona.json",
        "system_prompt.txt",
        "response.txt",
        "metadata.json",
    }

    persona = Persona.model_validate_json(
        (run_directory / "persona.json").read_text(encoding="utf-8")
    )
    assert persona.character_id == character_id
    assert persona.display_name == display_name

    system_prompt = (
        run_directory / "system_prompt.txt"
    ).read_text(encoding="utf-8")
    assert system_prompt.strip()
    assert persona.display_name in system_prompt
    assert persona.reasoning_style[0] in system_prompt

    response = (run_directory / "response.txt").read_text(encoding="utf-8")
    expected_response = (
        FIXTURE_DIRECTORY / f"{character}_agent_response.txt"
    ).read_text(encoding="utf-8")
    assert response.strip()
    assert response == expected_response

    metadata = json.loads(
        (run_directory / "metadata.json").read_text(encoding="utf-8")
    )
    assert metadata["provider"] == "mock"
    assert metadata["is_synthetic"] is True
    assert metadata["character_id"] == character_id
    assert metadata["character_slug"] == character
    assert metadata["model"] == "mock"
    assert metadata["user_message"] == user_message
    assert metadata["persona_file"] == "persona.json"
    assert metadata["system_prompt_file"] == "system_prompt.txt"
    assert metadata["response_file"] == "response.txt"
    saved_timestamp = datetime.fromisoformat(metadata["created_at"])
    assert saved_timestamp.tzinfo is not None
    assert saved_timestamp.utcoffset() == timezone.utc.utcoffset(None)
