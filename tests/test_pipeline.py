"""Tests for the unified synthetic mock pipeline."""

import json
import socket
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models.persona import Persona
from multi_agent_personalities.pipeline import (
    default_pipeline_paths,
    run_pipeline,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


def test_mock_pipeline_writes_valid_synthetic_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("The mock pipeline attempted network access")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    run_directory = run_pipeline(
        character="poirot",
        provider_name="mock",
        user_message="How would you begin investigating this case?",
        output_root=tmp_path,
        paths=default_pipeline_paths(PROJECT_ROOT),
        timestamp=FIXED_TIME,
    )

    expected_files = {
        "persona.json",
        "system_prompt.txt",
        "response.txt",
        "metadata.json",
    }
    assert {path.name for path in run_directory.iterdir()} == expected_files

    persona = Persona.model_validate_json(
        (run_directory / "persona.json").read_text(encoding="utf-8")
    )
    assert persona.display_name == "Hercule Poirot"

    metadata = json.loads(
        (run_directory / "metadata.json").read_text(encoding="utf-8")
    )
    assert metadata["provider"] == "mock"
    assert metadata["is_synthetic"] is True

    expected_response = (
        PROJECT_ROOT / "tests" / "fixtures" / "poirot_agent_response.txt"
    ).read_text(encoding="utf-8")
    assert (
        run_directory / "response.txt"
    ).read_text(encoding="utf-8") == expected_response


def test_rejects_unsupported_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported provider"):
        run_pipeline(
            character="poirot",
            provider_name="openai",
            user_message="Investigate this.",
            output_root=tmp_path,
            paths=default_pipeline_paths(PROJECT_ROOT),
        )


def test_rejects_invalid_mock_persona_response(tmp_path: Path) -> None:
    invalid_persona = tmp_path / "invalid_persona.json"
    invalid_persona.write_text(
        '{"character_id": "hercule_poirot"}',
        encoding="utf-8",
    )
    paths = replace(
        default_pipeline_paths(PROJECT_ROOT),
        persona_fixture=invalid_persona,
    )

    with pytest.raises(ValidationError):
        run_pipeline(
            character="poirot",
            provider_name="mock",
            user_message="Investigate this.",
            output_root=tmp_path / "outputs",
            paths=paths,
        )


def test_existing_run_is_not_overwritten(tmp_path: Path) -> None:
    arguments = {
        "character": "poirot",
        "provider_name": "mock",
        "user_message": "Investigate this.",
        "output_root": tmp_path,
        "paths": default_pipeline_paths(PROJECT_ROOT),
        "timestamp": FIXED_TIME,
    }
    run_directory = run_pipeline(**arguments)

    with pytest.raises(FileExistsError):
        run_pipeline(**arguments)

    assert (run_directory / "response.txt").is_file()
