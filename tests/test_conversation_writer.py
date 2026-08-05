"""Tests for complete conversation artifact persistence."""

import json
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

import multi_agent_personalities.artifacts.conversation_writer as writer_module
from multi_agent_personalities.artifacts import save_conversation_run
from multi_agent_personalities.models import (
    ConversationRun,
    GenerationMetadata,
    GenerationResult,
    Message,
    Persona,
)
from multi_agent_personalities.simulation import (
    ConversationParticipant,
    RoundRobinSelector,
    simulate_chat,
)


CREATED_AT = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)


class LocalProvider:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        return GenerationResult(
            text=self.response,
            metadata=GenerationMetadata(provider="mock"),
        )


def make_persona(character_id: str, display_name: str) -> Persona:
    return Persona(
        character_id=character_id,
        display_name=display_name,
        description=f"Description of {display_name}.",
        speaking_style=["Precise"],
        reasoning_style=["Methodical"],
        personality_traits=["Observant"],
        behavior_rules=["Address the topic"],
        example_messages=["An example."],
    )


def make_run(turn_count: int = 2) -> ConversationRun:
    return simulate_chat(
        participants=[
            ConversationParticipant(
                persona=make_persona("sherlock", "Sherlock Holmes"),
                provider=LocalProvider("Response 0."),
                provider_name="mock",
                model_name="mock-v1",
            ),
            ConversationParticipant(
                persona=make_persona("poirot", "Hercule Poirot"),
                provider=LocalProvider(
                    "Response 1, first paragraph.\n\nSecond paragraph."
                ),
                provider_name="mock",
                model_name="mock-v1",
            ),
        ],
        speaker_selector=RoundRobinSelector(),
        topic="A locked-room mystery",
        turn_count=turn_count,
        seed=42,
        run_id="run_fixed",
        timestamp=CREATED_AT,
    )


def test_writes_exact_files_and_round_trippable_models(tmp_path: Path) -> None:
    run = make_run()
    original_dump = run.model_dump_json()

    run_directory = save_conversation_run(output_root=tmp_path, run=run)

    assert run_directory == tmp_path / "conversations" / "runs" / "run_fixed"
    assert {path.name for path in run_directory.iterdir()} == {
        "run.json",
        "messages.jsonl",
        "transcript.md",
    }

    run_text = (run_directory / "run.json").read_text(encoding="utf-8")
    assert run_text.endswith("\n")
    assert ConversationRun.model_validate_json(run_text) == run

    message_text = (run_directory / "messages.jsonl").read_text(
        encoding="utf-8"
    )
    assert message_text.endswith("\n")
    lines = message_text.splitlines()
    reconstructed = [Message.model_validate_json(line) for line in lines]
    assert len(lines) == len(run.messages)
    assert reconstructed == list(run.messages)
    assert [message.turn_index for message in reconstructed] == [0, 1]
    expected_metadata = {
        "provider": "mock",
        "model": None,
        "usage": None,
        "finish_reason": None,
        "request_id": None,
        "latency_ms": None,
        "retry_count": 0,
    }
    run_payload = json.loads(run_text)
    assert all(
        message["generation_metadata"] == expected_metadata
        for message in run_payload["messages"]
    )
    assert all(
        json.loads(line)["generation_metadata"] == expected_metadata
        for line in lines
    )

    assert run.model_dump_json() == original_dump


def test_transcript_preserves_metadata_speakers_and_text(tmp_path: Path) -> None:
    run = make_run()
    run_directory = save_conversation_run(output_root=tmp_path, run=run)
    transcript = (run_directory / "transcript.md").read_text(
        encoding="utf-8"
    )

    assert transcript.endswith("\n")
    for expected in (
        "**Run ID:** run_fixed",
        "**Topic:** A locked-room mystery",
        "**Status:** completed",
        "**Provider:** mock",
        "**Model:** mock-v1",
        "**Seed:** 42",
        "**Created at:** 2026-08-03T12:00:00+00:00",
        "## Turn 0 — Sherlock Holmes",
        "## Turn 1 — Hercule Poirot",
    ):
        assert expected in transcript
    for message in run.messages:
        assert transcript.count(message.text) == 1
    assert "Response 1, first paragraph.\n\nSecond paragraph." in transcript
    assert "generation_metadata" not in transcript
    assert "retry_count" not in transcript


def test_transcript_records_textless_generation_error(tmp_path: Path) -> None:
    message = Message(
        message_id="failed_message_0000",
        run_id="failed",
        turn_index=0,
        speaker_character_id="sherlock",
        speaker_name="Sherlock Holmes",
        text="",
        provider="mock",
        timestamp=CREATED_AT,
        error="provider unavailable",
    )
    run = ConversationRun(
        run_id="failed",
        topic="A mystery",
        character_ids=("sherlock", "poirot"),
        turn_count=2,
        seed=1,
        provider="mock",
        created_at=CREATED_AT,
        status="failed",
        messages=(message,),
    )

    directory = save_conversation_run(output_root=tmp_path, run=run)
    transcript = (directory / "transcript.md").read_text(encoding="utf-8")
    assert "_Generation error: provider unavailable_" in transcript
    assert "**Model:**" not in transcript


def test_existing_run_is_not_overwritten(tmp_path: Path) -> None:
    run = make_run()
    directory = save_conversation_run(output_root=tmp_path, run=run)
    original = (directory / "run.json").read_text(encoding="utf-8")

    with pytest.raises(FileExistsError):
        save_conversation_run(output_root=tmp_path, run=run)

    assert (directory / "run.json").read_text(encoding="utf-8") == original
    assert {path.name for path in directory.iterdir()} == {
        "run.json", "messages.jsonl", "transcript.md",
    }
    assert {path.name for path in directory.parent.iterdir()} == {run.run_id}


def test_existing_reservation_rejects_before_temporary_directory_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = make_run()
    runs_directory = tmp_path / "conversations" / "runs"
    runs_directory.mkdir(parents=True)
    lock_path = runs_directory / f".{run.run_id}.lock"
    lock_path.touch()

    def reject_mkdtemp(*args: object, **kwargs: object) -> str:
        raise AssertionError("temporary directory must not be created")

    monkeypatch.setattr(writer_module.tempfile, "mkdtemp", reject_mkdtemp)
    with pytest.raises(FileExistsError, match="reserved"):
        save_conversation_run(output_root=tmp_path, run=run)

    assert list(runs_directory.iterdir()) == [lock_path]


def test_simulation_and_persistence_are_network_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    run = make_run(turn_count=6)
    directory = save_conversation_run(output_root=tmp_path, run=run)

    assert len(run.messages) == 6
    assert len(
        (directory / "messages.jsonl").read_text(encoding="utf-8").splitlines()
    ) == 6


def test_conversation_models_remain_immutable() -> None:
    run = make_run()
    with pytest.raises(ValidationError):
        run.topic = "Changed"
    with pytest.raises(ValidationError):
        run.messages[0].text = "Changed"


def test_writer_defensively_rejects_traversal_run_id(tmp_path: Path) -> None:
    run = make_run().model_copy(update={"run_id": "../outside"})

    with pytest.raises(ValueError, match="run_id"):
        save_conversation_run(output_root=tmp_path, run=run)

    assert not (tmp_path / "outside").exists()


def test_failed_write_leaves_no_final_or_temporary_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = make_run()

    def fail_render(run: ConversationRun) -> str:
        raise OSError("simulated transcript failure")

    monkeypatch.setattr(writer_module, "_render_transcript", fail_render)
    with pytest.raises(OSError, match="simulated transcript failure"):
        save_conversation_run(output_root=tmp_path, run=run)

    runs_directory = tmp_path / "conversations" / "runs"
    assert not (runs_directory / run.run_id).exists()
    assert list(runs_directory.iterdir()) == []


def test_concurrent_writers_cannot_both_publish_same_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = make_run()
    temporary_created = threading.Event()
    allow_first_writer = threading.Event()
    real_mkdtemp = writer_module.tempfile.mkdtemp

    def coordinated_mkdtemp(*args: object, **kwargs: object) -> str:
        path = real_mkdtemp(*args, **kwargs)
        temporary_created.set()
        assert allow_first_writer.wait(timeout=5)
        return path

    monkeypatch.setattr(writer_module.tempfile, "mkdtemp", coordinated_mkdtemp)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            save_conversation_run, output_root=tmp_path, run=run
        )
        assert temporary_created.wait(timeout=5)
        second = executor.submit(
            save_conversation_run, output_root=tmp_path, run=run
        )
        with pytest.raises(FileExistsError):
            second.result(timeout=5)
        allow_first_writer.set()
        directory = first.result(timeout=5)

    assert ConversationRun.model_validate_json(
        (directory / "run.json").read_text(encoding="utf-8")
    ) == run
    assert {path.name for path in directory.iterdir()} == {
        "run.json", "messages.jsonl", "transcript.md",
    }
    assert {path.name for path in directory.parent.iterdir()} == {run.run_id}
