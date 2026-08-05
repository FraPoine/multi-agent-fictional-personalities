"""Tests for the framework-independent conversation application service."""

import socket
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

import multi_agent_personalities.application.conversation_service as service_module
from multi_agent_personalities.application import (
    ConversationResult,
    run_mock_conversation,
)
from multi_agent_personalities.llm import MockProvider
from multi_agent_personalities.models import ConversationRun, Message, Persona
from multi_agent_personalities.pipeline import character_registry


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TOPIC = "A valuable document disappeared from a locked room."
EXPECTED_FILES = {"run.json", "messages.jsonl", "transcript.md"}
SYNTHETIC_CHARACTERS = (
    ("alpha", "agent-alpha", "Agent Alpha"),
    ("beta", "agent-beta", "Agent Beta"),
    ("gamma", "agent-gamma", "Agent Gamma"),
)


class SequenceSelector:
    def __init__(self, selections: Sequence[str]) -> None:
        self.selections = tuple(selections)

    def select_next(
        self,
        *,
        participant_ids: Sequence[str],
        history: Sequence[Message],
        turn_index: int,
    ) -> str:
        return self.selections[turn_index]


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


def create_synthetic_project(project_root: Path) -> None:
    """Create a three-character catalog and assets entirely under ``tmp_path``."""

    config_directory = project_root / "configs"
    asset_directory = project_root / "synthetic_assets"
    config_directory.mkdir(parents=True)
    entries: list[dict[str, str]] = []

    for slug, character_id, display_name in SYNTHETIC_CHARACTERS:
        character_directory = asset_directory / slug
        character_directory.mkdir(parents=True)
        (character_directory / "corpus.jsonl").write_text(
            '{"text":"Synthetic test evidence."}\n',
            encoding="utf-8",
        )
        persona = Persona(
            character_id=character_id,
            display_name=display_name,
            description="A synthetic persona used only for service tests.",
            speaking_style=["Neutral"],
            reasoning_style=["Deterministic"],
            personality_traits=["Test-only"],
            behavior_rules=["Use only the supplied test context"],
            example_messages=[f"response-from-{slug}"],
        )
        (character_directory / "persona.json").write_text(
            persona.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        (character_directory / "response.txt").write_text(
            f"response-from-{slug}\n",
            encoding="utf-8",
        )
        entries.append(
            {
                "slug": slug,
                "character_id": character_id,
                "display_name": display_name,
                "description": "Synthetic service-test character.",
                "corpus_path": f"../synthetic_assets/{slug}/corpus.jsonl",
                "persona_fixture_path": (
                    f"../synthetic_assets/{slug}/persona.json"
                ),
                "mock_response_fixture_path": (
                    f"../synthetic_assets/{slug}/response.txt"
                ),
            }
        )

    (config_directory / "characters.yaml").write_text(
        yaml.safe_dump({"characters": entries}, sort_keys=False),
        encoding="utf-8",
    )


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
    expected_text = {
        "sherlock_holmes": (
            REPOSITORY_ROOT / "tests" / "fixtures" / "sherlock_agent_response.txt"
        ).read_text(encoding="utf-8"),
        "hercule_poirot": (
            REPOSITORY_ROOT / "tests" / "fixtures" / "poirot_agent_response.txt"
        ).read_text(encoding="utf-8"),
    }
    assert all(
        message.text == expected_text[message.speaker_character_id]
        for message in result.run.messages
    )


def test_service_builds_one_file_backed_provider_per_participant() -> None:
    participants = service_module._load_mock_participants(
        ["sherlock", "poirot"],
        REPOSITORY_ROOT,
    )

    assert all(isinstance(item.provider, MockProvider) for item in participants)
    assert participants[0].provider is not participants[1].provider
    assert [item.provider_name for item in participants] == ["mock", "mock"]
    assert [item.model_name for item in participants] == [
        "mock-round-robin",
        "mock-round-robin",
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
    expected_text = [
        (
            REPOSITORY_ROOT / "tests" / "fixtures" / "poirot_agent_response.txt"
        ).read_text(encoding="utf-8"),
        (
            REPOSITORY_ROOT / "tests" / "fixtures" / "sherlock_agent_response.txt"
        ).read_text(encoding="utf-8"),
    ]
    assert [message.text for message in result.run.messages] == expected_text * 2


def test_three_catalog_participants_flow_through_service_and_artifacts(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "synthetic_project"
    output_root = tmp_path / "outputs"
    create_synthetic_project(project_root)

    result = run_mock_conversation(
        character_slugs=["gamma", "alpha", "beta"],
        topic="A synthetic boundary-verification case.",
        turn_count=5,
        seed=42,
        output_root=output_root,
        project_root=project_root,
        run_id="three_participant_service_run",
        timestamp=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
    )

    expected_ids = (
        "agent-gamma",
        "agent-alpha",
        "agent-beta",
    )
    expected_speakers = [
        "agent-gamma",
        "agent-alpha",
        "agent-beta",
        "agent-gamma",
        "agent-alpha",
    ]
    expected_text = [
        "response-from-gamma\n",
        "response-from-alpha\n",
        "response-from-beta\n",
        "response-from-gamma\n",
        "response-from-alpha\n",
    ]

    assert result.run.status == "completed"
    assert result.run.character_ids == expected_ids
    assert result.run.turn_count == 5
    assert [message.speaker_character_id for message in result.run.messages] == (
        expected_speakers
    )
    assert [message.text for message in result.run.messages] == expected_text
    assert all(
        message.speaker_character_id in result.run.character_ids
        for message in result.run.messages
    )

    run = ConversationRun.model_validate_json(
        (result.artifact_directory / "run.json").read_text(encoding="utf-8")
    )
    messages = [
        Message.model_validate_json(line)
        for line in (result.artifact_directory / "messages.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert run.character_ids == expected_ids
    assert [message.speaker_character_id for message in messages] == (
        expected_speakers
    )
    assert all(
        message.speaker_character_id in run.character_ids
        for message in messages
    )

    transcript = (result.artifact_directory / "transcript.md").read_text(
        encoding="utf-8"
    )
    assert all(
        display_name in transcript
        for _, _, display_name in SYNTHETIC_CHARACTERS
    )
    assert "Sherlock" not in transcript
    assert "Poirot" not in transcript


def test_injected_selector_controls_persisted_order_and_fixture_ownership(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "synthetic_project"
    output_root = tmp_path / "outputs"
    create_synthetic_project(project_root)
    selections = [
        "agent-alpha",
        "agent-alpha",
        "agent-gamma",
        "agent-beta",
        "agent-gamma",
    ]

    result = run_mock_conversation(
        character_slugs=["alpha", "beta", "gamma"],
        speaker_selector=SequenceSelector(selections),
        topic=TOPIC,
        turn_count=5,
        output_root=output_root,
        project_root=project_root,
        run_id="custom_selector_run",
    )

    assert result.run.character_ids == (
        "agent-alpha",
        "agent-beta",
        "agent-gamma",
    )
    assert [message.speaker_character_id for message in result.run.messages] == (
        selections
    )
    assert [message.text for message in result.run.messages] == [
        f"response-from-{character_id.removeprefix('agent-')}\n"
        for character_id in selections
    ]
    persisted = ConversationRun.model_validate_json(
        (result.artifact_directory / "run.json").read_text(encoding="utf-8")
    )
    assert persisted == result.run


def test_invalid_injected_selector_prevents_completed_artifacts(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "synthetic_project"
    output_root = tmp_path / "outputs"
    create_synthetic_project(project_root)

    with pytest.raises(ValueError, match="unsupported participant identifier"):
        run_mock_conversation(
            character_slugs=["alpha", "beta", "gamma"],
            speaker_selector=SequenceSelector(["unknown-participant"]),
            topic=TOPIC,
            turn_count=1,
            output_root=output_root,
            project_root=project_root,
            run_id="invalid_selector_run",
        )

    assert_no_completed_run(output_root)


def test_injected_selector_exception_prevents_completed_artifacts(
    tmp_path: Path,
) -> None:
    class SelectorFailure(RuntimeError):
        pass

    class FailingSelector:
        def select_next(
            self,
            *,
            participant_ids: Sequence[str],
            history: Sequence[Message],
            turn_index: int,
        ) -> str:
            raise SelectorFailure("selection unavailable")

    output_root = tmp_path / "outputs"
    with pytest.raises(SelectorFailure, match="selection unavailable"):
        run_service(
            output_root,
            run_id="failing_selector_run",
            turn_count=1,
            speaker_selector=FailingSelector(),
        )

    assert_no_completed_run(output_root)


def test_unknown_participant_in_injected_catalog_fails_without_artifacts(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "synthetic_project"
    output_root = tmp_path / "outputs"
    create_synthetic_project(project_root)

    with pytest.raises(
        ValueError,
        match="unsupported character: 'unknown'.*alpha, beta, gamma",
    ):
        run_mock_conversation(
            character_slugs=["gamma", "unknown", "alpha"],
            topic=TOPIC,
            turn_count=5,
            output_root=output_root,
            project_root=project_root,
            run_id="unknown_synthetic_participant_run",
        )

    assert_no_completed_run(output_root)


@pytest.mark.parametrize(
    ("character_slugs", "error"),
    [
        (["alpha"], "at least two"),
        (["alpha", "beta", "alpha"], "must not contain duplicates"),
    ],
)
def test_injected_catalog_rejects_invalid_participant_collection(
    tmp_path: Path,
    character_slugs: list[str],
    error: str,
) -> None:
    project_root = tmp_path / "synthetic_project"
    output_root = tmp_path / "outputs"
    create_synthetic_project(project_root)

    with pytest.raises(ValueError, match=error):
        run_mock_conversation(
            character_slugs=character_slugs,
            topic=TOPIC,
            turn_count=5,
            output_root=output_root,
            project_root=project_root,
            run_id="invalid_synthetic_participants_run",
        )

    assert_no_completed_run(output_root)


@pytest.mark.parametrize("character_slugs", [[], ["sherlock"]])
def test_rejects_fewer_than_two_characters(
    tmp_path: Path,
    character_slugs: list[str],
) -> None:
    with pytest.raises(ValueError, match="at least two"):
        run_service(
            tmp_path,
            run_id="too_few_run",
            character_slugs=character_slugs,
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
