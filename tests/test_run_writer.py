"""Tests for canonical single-agent run artifact persistence."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from multi_agent_personalities.artifacts import save_single_agent_run
from multi_agent_personalities.models.message import Message
from multi_agent_personalities.models.persona import Persona


CREATED_AT = datetime(2026, 7, 28, 8, 30, tzinfo=timezone.utc)


def make_persona() -> Persona:
    return Persona(
        character_id="hercule_poirot",
        display_name="Hercule Poirot",
        description="A methodical Belgian detective.",
        speaking_style=["Precise"],
        reasoning_style=["Psychological"],
        personality_traits=["Orderly"],
        behavior_rules=["Attend to every fact"],
        example_messages=["Use the little grey cells."],
    )


def make_response(**overrides: object) -> Message:
    values: dict[str, object] = {
        "message_id": "test-run-001_message_0000",
        "run_id": "test-run-001",
        "turn_index": 0,
        "speaker_character_id": "hercule_poirot",
        "speaker_name": "Hercule Poirot",
        "text": "Ah, mon ami.\nThe facts are exact.",
        "provider": "mock",
        "model": "mock-agent-v1",
        "timestamp": CREATED_AT,
        "error": None,
    }
    values.update(overrides)
    return Message.model_validate(values)


def save_run(tmp_path: Path, **overrides: object) -> Path:
    arguments: dict[str, object] = {
        "output_root": tmp_path,
        "character_slug": "poirot",
        "run_id": "test-run-001",
        "created_at": CREATED_AT,
        "persona": make_persona(),
        "system_prompt": "You are Hercule Poirot.\n",
        "response": make_response(),
        "user_message": "What do you observe?",
        "is_synthetic": True,
    }
    arguments.update(overrides)
    return save_single_agent_run(**arguments)  # type: ignore[arg-type]


def test_saves_canonical_files_and_metadata(tmp_path: Path) -> None:
    run_directory = save_run(tmp_path)

    assert run_directory == tmp_path / "poirot" / "runs" / "test-run-001"
    assert {path.name for path in run_directory.iterdir()} == {
        "persona.json",
        "system_prompt.txt",
        "response.txt",
        "metadata.json",
    }
    assert (run_directory / "response.txt").read_text(
        encoding="utf-8"
    ) == "Ah, mon ami.\nThe facts are exact."
    assert Persona.model_validate_json(
        (run_directory / "persona.json").read_text(encoding="utf-8")
    ) == make_persona()

    metadata_text = (run_directory / "metadata.json").read_text(
        encoding="utf-8"
    )
    assert metadata_text.endswith("\n")
    assert json.loads(metadata_text) == {
        "run_id": "test-run-001",
        "created_at": "2026-07-28T08:30:00+00:00",
        "character_id": "hercule_poirot",
        "character_slug": "poirot",
        "task_name": "agent_reply",
        "provider": "mock",
        "model": "mock-agent-v1",
        "is_synthetic": True,
        "user_message": "What do you observe?",
        "persona_file": "persona.json",
        "system_prompt_file": "system_prompt.txt",
        "response_file": "response.txt",
    }


def test_existing_run_directory_is_not_overwritten(tmp_path: Path) -> None:
    run_directory = save_run(tmp_path)

    with pytest.raises(FileExistsError):
        save_run(tmp_path)

    assert (run_directory / "response.txt").read_text(
        encoding="utf-8"
    ).startswith("Ah, mon ami")


@pytest.mark.parametrize(
    "field_name",
    ["character_slug", "run_id", "system_prompt", "user_message"],
)
def test_rejects_empty_required_text(
    tmp_path: Path,
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match=f"{field_name} cannot be empty"):
        save_run(tmp_path, **{field_name: " \t "})


def test_rejects_timezone_naive_created_at(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="created_at must be timezone-aware"):
        save_run(tmp_path, created_at=datetime(2026, 7, 28, 8, 30))


def test_rejects_inconsistent_message_identity(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="response run_id"):
        save_run(tmp_path, response=make_response(run_id="other-run"))

    with pytest.raises(ValueError, match="response character_id"):
        save_run(
            tmp_path,
            response=make_response(speaker_character_id="sherlock_holmes"),
        )
