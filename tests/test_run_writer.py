"""Tests for agent run artifact persistence."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from multi_agent_personalities.artifacts import save_agent_run


def test_saves_response_and_metadata_in_run_directory(
    tmp_path: Path,
) -> None:
    response = "Ah, mon ami.\nThe facts are exact."
    created_at = datetime(2026, 7, 28, 8, 30, tzinfo=timezone.utc)

    run_directory = save_agent_run(
        output_root=tmp_path,
        character_id="hercule_poirot",
        response_text=response,
        provider_name="mock",
        model_name="mock-agent-v1",
        is_synthetic=True,
        run_id="test-run-001",
        created_at=created_at,
    )

    assert run_directory == (
        tmp_path / "hercule_poirot" / "runs" / "test-run-001"
    )
    assert run_directory.is_dir()
    assert (run_directory / "response.txt").read_text(
        encoding="utf-8"
    ) == response

    metadata = json.loads(
        (run_directory / "metadata.json").read_text(encoding="utf-8")
    )
    assert metadata == {
        "run_id": "test-run-001",
        "created_at": "2026-07-28T08:30:00+00:00",
        "character_id": "hercule_poirot",
        "task_name": "agent_reply",
        "provider": "mock",
        "model": "mock-agent-v1",
        "is_synthetic": True,
        "response_file": "response.txt",
    }


def test_generates_run_id_and_utc_timestamp(tmp_path: Path) -> None:
    run_directory = save_agent_run(
        output_root=tmp_path,
        character_id="sherlock_holmes",
        response_text="The evidence is sufficient.",
        provider_name="local",
        model_name="test-model",
        is_synthetic=True,
    )

    metadata = json.loads(
        (run_directory / "metadata.json").read_text(encoding="utf-8")
    )
    saved_timestamp = datetime.fromisoformat(metadata["created_at"])

    assert metadata["run_id"] == run_directory.name
    assert metadata["run_id"]
    assert saved_timestamp.tzinfo is not None
    assert saved_timestamp.utcoffset() == timezone.utc.utcoffset(None)


def test_existing_run_directory_is_not_overwritten(
    tmp_path: Path,
) -> None:
    arguments = {
        "output_root": tmp_path,
        "character_id": "hercule_poirot",
        "response_text": "Original response",
        "provider_name": "mock",
        "model_name": "mock-agent-v1",
        "is_synthetic": True,
        "run_id": "existing-run",
    }
    run_directory = save_agent_run(**arguments)

    with pytest.raises(FileExistsError):
        save_agent_run(**{**arguments, "response_text": "Replacement"})

    assert (run_directory / "response.txt").read_text(
        encoding="utf-8"
    ) == "Original response"


@pytest.mark.parametrize(
    ("field_name", "empty_value"),
    [
        ("character_id", ""),
        ("response_text", "   "),
        ("provider_name", "\t"),
        ("model_name", "\n"),
    ],
)
def test_rejects_empty_required_values(
    tmp_path: Path,
    field_name: str,
    empty_value: str,
) -> None:
    arguments = {
        "output_root": tmp_path,
        "character_id": "hercule_poirot",
        "response_text": "A response",
        "provider_name": "mock",
        "model_name": "mock-agent-v1",
        "is_synthetic": True,
    }
    arguments[field_name] = empty_value

    with pytest.raises(ValueError, match=f"{field_name} cannot be empty"):
        save_agent_run(**arguments)


def test_rejects_timezone_naive_created_at(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError,
        match="created_at must be timezone-aware",
    ):
        save_agent_run(
            output_root=tmp_path,
            character_id="hercule_poirot",
            response_text="A response",
            provider_name="mock",
            model_name="mock-agent-v1",
            is_synthetic=True,
            created_at=datetime(2026, 7, 28, 8, 30),
        )
