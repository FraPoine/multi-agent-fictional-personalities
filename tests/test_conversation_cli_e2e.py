"""Subprocess coverage for the complete local conversation CLI path."""

import os
import subprocess
import sys
from pathlib import Path

from multi_agent_personalities.models import ConversationRun, Message


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _command(output_root: Path) -> list[str]:
    return [
        sys.executable,
        "scripts/run_conversation.py",
        "--characters", "sherlock", "poirot",
        "--topic", "A valuable document disappeared from a locked room.",
        "--turn-count", "6",
        "--provider", "mock",
        "--seed", "42",
        "--output-root", str(output_root),
        "--run-id", "e2e_6_turns",
    ]


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    source = str(REPOSITORY_ROOT / "src")
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source if not existing else source + os.pathsep + existing
    )
    return environment


def test_six_turn_cli_and_duplicate_invocation(tmp_path: Path) -> None:
    command = _command(tmp_path)
    first = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=_environment(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert first.returncode == 0
    assert "Conversation completed." in first.stdout
    assert first.stderr == ""

    runs_directory = tmp_path / "conversations" / "runs"
    run_directory = runs_directory / "e2e_6_turns"
    expected_files = {"run.json", "messages.jsonl", "transcript.md"}
    assert run_directory.is_dir()
    assert {path.name for path in run_directory.iterdir()} == expected_files
    assert {path.name for path in runs_directory.iterdir()} == {"e2e_6_turns"}

    run = ConversationRun.model_validate_json(
        (run_directory / "run.json").read_text(encoding="utf-8")
    )
    assert run.status == "completed"
    assert len(run.messages) == 6
    assert [message.turn_index for message in run.messages] == list(range(6))
    assert [message.speaker_character_id for message in run.messages] == [
        "sherlock_holmes", "hercule_poirot",
        "sherlock_holmes", "hercule_poirot",
        "sherlock_holmes", "hercule_poirot",
    ]
    assert run.provider == "mock"
    assert run.model == "mock-round-robin"
    assert run.seed == 42

    lines = [
        line for line in
        (run_directory / "messages.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    messages = [Message.model_validate_json(line) for line in lines]
    assert len(messages) == 6
    assert messages == list(run.messages)
    assert {message.run_id for message in messages} == {run.run_id}

    transcript = (run_directory / "transcript.md").read_text(encoding="utf-8")
    assert "Sherlock Holmes" in transcript
    assert "Hercule Poirot" in transcript
    for turn_index in range(6):
        assert f"## Turn {turn_index} —" in transcript

    originals = {
        name: (run_directory / name).read_bytes() for name in expected_files
    }
    second = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=_environment(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert second.returncode != 0
    assert "already exists" in second.stderr
    assert "Traceback" not in second.stderr
    assert "Conversation completed." not in second.stdout
    assert {
        name: (run_directory / name).read_bytes() for name in expected_files
    } == originals
    assert {path.name for path in runs_directory.iterdir()} == {"e2e_6_turns"}
