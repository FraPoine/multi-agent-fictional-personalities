"""Tests for the framework-independent conversation application service."""

import socket
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

import multi_agent_personalities.application.conversation_service as service_module
from multi_agent_personalities.application import (
    ConversationResult,
    run_mock_conversation,
)
from multi_agent_personalities.models import ConversationRun, Message, Persona
from multi_agent_personalities.pipeline import character_registry


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TOPIC = "A valuable document disappeared from a locked room."
EXPECTED_FILES = {"run.json", "messages.jsonl", "transcript.md"}


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail every service test if conversation execution attempts a network."""

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)


def run_service(
    output_root: Path,
    *,
    run_id: str,
    **overrides: Any,
) -> ConversationResult:
    arguments: dict[str, Any] = {
        "character_slugs": ["sherlock", "poirot"],
        "topic": TOPIC,
        "turn_count": 6,
        "seed": 42,
        "output_root": output_root,
        "project_root": REPOSITORY_ROOT,
        "run_id": run_id,
    }
    arguments.update(overrides)
    return run_mock_conversation(**arguments)


def assert_no_completed_run(output_root: Path) -> None:
    runs_directory = output_root / "conversations" / "runs"
    assert not runs_directory.exists() or list(runs_directory.iterdir()) == []


def replace_registry_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    slug: str,
    persona_fixture: Path | None = None,
    response_fixture: Path | None = None,
) -> None:
    registry = character_registry(REPOSITORY_ROOT)
    config = registry[slug]
    registry[slug] = replace(
        config,
        persona_fixture=(
            config.persona_fixture
            if persona_fixture is None
            else persona_fixture
        ),
        agent_response_fixture=(
            config.agent_response_fixture
            if response_fixture is None
            else response_fixture
        ),
    )
    monkeypatch.setattr(
        service_module,
        "character_registry",
        lambda project_root: registry,
    )


def test_successful_conversation_execution(tmp_path: Path) -> None:
    result = run_service(tmp_path, run_id="service_test_run")

    assert isinstance(result, ConversationResult)
    assert result.run_id == "service_test_run"
    assert result.run.status == "completed"
    assert result.run.provider == "mock"
    assert result.run.model == "mock-round-robin"
    assert result.run.seed == 42
    assert result.run.turn_count == 6
    assert result.run.topic == TOPIC
    assert len(result.run.messages) == 6
    assert [message.turn_index for message in result.run.messages] == list(range(6))
    assert [
        message.speaker_character_id for message in result.run.messages
    ] == [
        "sherlock_holmes",
        "hercule_poirot",
        "sherlock_holmes",
        "hercule_poirot",
        "sherlock_holmes",
        "hercule_poirot",
    ]


def test_artifact_creation_and_result_paths(tmp_path: Path) -> None:
    result = run_service(tmp_path, run_id="artifact_test_run")
    expected_directory = (
        tmp_path / "conversations" / "runs" / "artifact_test_run"
    )

    assert result.artifact_directory == expected_directory
    assert result.artifact_directory.is_dir()
    assert {path.name for path in result.artifact_directory.iterdir()} == (
        EXPECTED_FILES
    )
    assert result.transcript_path == expected_directory / "transcript.md"
    assert set(result.artifact_paths) == {
        expected_directory / filename for filename in EXPECTED_FILES
    }
    assert all(
        path.parent == result.artifact_directory
        for path in result.artifact_paths
    )


def test_persisted_content_matches_result(tmp_path: Path) -> None:
    result = run_service(tmp_path, run_id="content_test_run")
    directory = result.artifact_directory

    persisted_run = ConversationRun.model_validate_json(
        (directory / "run.json").read_text(encoding="utf-8")
    )
    assert persisted_run == result.run

    lines = [
        line
        for line in (directory / "messages.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    persisted_messages = [Message.model_validate_json(line) for line in lines]
    assert len(lines) == len(result.run.messages)
    assert persisted_messages == list(result.run.messages)

    transcript = result.transcript_path.read_text(encoding="utf-8")
    assert "Sherlock Holmes" in transcript
    assert "Hercule Poirot" in transcript
    assert result.run_id in transcript
    assert TOPIC in transcript
    for turn_index in range(6):
        assert f"## Turn {turn_index} —" in transcript


def test_character_input_order_is_preserved(tmp_path: Path) -> None:
    result = run_service(
        tmp_path,
        run_id="reverse_order_run",
        character_slugs=["poirot", "sherlock"],
        turn_count=4,
    )

    assert result.run.character_ids == ("hercule_poirot", "sherlock_holmes")
    assert [
        message.speaker_character_id for message in result.run.messages
    ] == [
        "hercule_poirot",
        "sherlock_holmes",
        "hercule_poirot",
        "sherlock_holmes",
    ]


def test_rejects_fewer_than_two_characters(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least two"):
        run_service(
            tmp_path,
            run_id="too_few_run",
            character_slugs=["sherlock"],
        )

    assert_no_completed_run(tmp_path)


def test_rejects_duplicate_characters(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicates"):
        run_service(
            tmp_path,
            run_id="duplicate_characters_run",
            character_slugs=["sherlock", "sherlock"],
        )

    assert_no_completed_run(tmp_path)


def test_rejects_unsupported_character(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported character: 'unknown'"):
        run_service(
            tmp_path,
            run_id="unsupported_character_run",
            character_slugs=["sherlock", "unknown"],
        )

    assert_no_completed_run(tmp_path)


@pytest.mark.parametrize(
    "character_slugs",
    ["sherlock", ["sherlock", 123]],
)
def test_rejects_invalid_character_collection_types(
    tmp_path: Path,
    character_slugs: object,
) -> None:
    with pytest.raises((TypeError, ValueError), match="sequence|strings"):
        run_service(
            tmp_path,
            run_id="invalid_collection_run",
            character_slugs=character_slugs,
        )

    assert_no_completed_run(tmp_path)


@pytest.mark.parametrize("topic", ["", "   ", "\n\t"])
def test_rejects_empty_topic(tmp_path: Path, topic: str) -> None:
    with pytest.raises(ValueError, match="topic must not be empty"):
        run_service(tmp_path, run_id="empty_topic_run", topic=topic)

    assert_no_completed_run(tmp_path)


@pytest.mark.parametrize("turn_count", [0, -1, 1.5])
def test_rejects_invalid_turn_count(
    tmp_path: Path,
    turn_count: object,
) -> None:
    with pytest.raises(ValueError, match="turn_count"):
        run_service(
            tmp_path,
            run_id="invalid_turn_count_run",
            turn_count=turn_count,
        )

    assert_no_completed_run(tmp_path)


def test_duplicate_run_does_not_change_artifacts_or_leave_debris(
    tmp_path: Path,
) -> None:
    result = run_service(tmp_path, run_id="duplicate_run_test")
    originals = {
        path.name: path.read_bytes() for path in result.artifact_paths
    }

    with pytest.raises(FileExistsError, match="already exists"):
        run_service(tmp_path, run_id="duplicate_run_test")

    assert {
        path.name: path.read_bytes() for path in result.artifact_paths
    } == originals
    runs_directory = result.artifact_directory.parent
    assert {path.name for path in runs_directory.iterdir()} == {
        "duplicate_run_test"
    }


def test_rejects_invalid_persona_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_persona = tmp_path / "invalid_persona.json"
    invalid_persona.write_text("{malformed", encoding="utf-8")
    replace_registry_fixture(
        monkeypatch,
        slug="sherlock",
        persona_fixture=invalid_persona,
    )
    output_root = tmp_path / "outputs"

    with pytest.raises(
        ValueError,
        match="invalid synthetic persona fixture for 'sherlock'",
    ):
        run_service(output_root, run_id="invalid_persona_run")

    assert_no_completed_run(output_root)


def test_rejects_persona_identity_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sherlock_config = character_registry(REPOSITORY_ROOT)["sherlock"]
    persona = Persona.model_validate_json(
        sherlock_config.persona_fixture.read_text(encoding="utf-8")
    ).model_copy(update={"character_id": "not_sherlock_holmes"})
    mismatched_persona = tmp_path / "mismatched_persona.json"
    mismatched_persona.write_text(
        persona.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    replace_registry_fixture(
        monkeypatch,
        slug="sherlock",
        persona_fixture=mismatched_persona,
    )
    output_root = tmp_path / "outputs"

    with pytest.raises(ValueError, match="identity does not match 'sherlock'"):
        run_service(output_root, run_id="identity_mismatch_run")

    assert_no_completed_run(output_root)


@pytest.mark.parametrize("fixture_state", ["missing", "whitespace"])
def test_rejects_invalid_response_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixture_state: str,
) -> None:
    response_fixture = tmp_path / f"{fixture_state}_response.txt"
    if fixture_state == "whitespace":
        response_fixture.write_text(" \n\t", encoding="utf-8")
    replace_registry_fixture(
        monkeypatch,
        slug="sherlock",
        response_fixture=response_fixture,
    )
    output_root = tmp_path / "outputs"

    expected = (
        "invalid synthetic response fixture"
        if fixture_state == "missing"
        else "synthetic response fixture for 'sherlock' is empty"
    )
    with pytest.raises(ValueError, match=expected):
        run_service(output_root, run_id=f"{fixture_state}_response_run")

    assert_no_completed_run(output_root)


def test_explicit_timestamp_propagation_and_naive_rejection(
    tmp_path: Path,
) -> None:
    timestamp = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    result = run_service(
        tmp_path,
        run_id="fixed_timestamp_run",
        timestamp=timestamp,
    )

    assert result.run.created_at == timestamp
    assert all(message.timestamp == timestamp for message in result.run.messages)

    with pytest.raises(ValueError, match="timezone-aware"):
        run_service(
            tmp_path,
            run_id="naive_timestamp_run",
            timestamp=datetime(2026, 8, 3, 12, 0),
        )
    assert not (
        tmp_path / "conversations" / "runs" / "naive_timestamp_run"
    ).exists()
