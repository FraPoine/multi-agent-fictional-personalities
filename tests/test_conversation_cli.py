"""Tests for the importable synthetic conversation command."""

import socket
from pathlib import Path

import pytest

from multi_agent_personalities.cli.conversation import main
from multi_agent_personalities.models import ConversationRun, Message


def arguments(output_root: Path, *extra: str) -> list[str]:
    return [
        "--characters", "sherlock", "poirot",
        "--topic", "A valuable document disappeared from a locked room.",
        "--output-root", str(output_root),
        "--run-id", "run_001",
        *extra,
    ]


def test_cli_creates_complete_six_turn_round_robin_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    assert main(arguments(tmp_path)) == 0
    captured = capsys.readouterr()
    assert "Conversation completed." in captured.out
    assert "Run ID: run_001" in captured.out
    assert captured.err == ""

    directory = tmp_path / "conversations" / "runs" / "run_001"
    assert {path.name for path in directory.iterdir()} == {
        "run.json", "messages.jsonl", "transcript.md",
    }
    run = ConversationRun.model_validate_json(
        (directory / "run.json").read_text(encoding="utf-8")
    )
    messages = [
        Message.model_validate_json(line)
        for line in (directory / "messages.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(run.messages) == len(messages) == 6
    assert run.provider == "mock"
    assert run.model == "mock-round-robin"
    assert [message.speaker_character_id for message in messages] == [
        "sherlock_holmes", "hercule_poirot",
        "sherlock_holmes", "hercule_poirot",
        "sherlock_holmes", "hercule_poirot",
    ]
    transcript = (directory / "transcript.md").read_text(encoding="utf-8")
    assert "Sherlock Holmes" in transcript
    assert "Hercule Poirot" in transcript


@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (["--characters", "sherlock"], "at least two characters"),
        (
            ["--characters", "sherlock", "sherlock"],
            "must not contain duplicates",
        ),
        (["--characters", "sherlock", "layton"], "unsupported character"),
        (
            ["--characters", "sherlock", "poirot", "--provider", "openai"],
            "unsupported provider",
        ),
        (
            ["--characters", "sherlock", "poirot", "--run-id", "../outside"],
            "run_id",
        ),
    ],
)
def test_cli_returns_nonzero_for_user_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    error: str,
) -> None:
    complete_argv = [*argv, "--topic", "A mystery", "--output-root", str(tmp_path)]
    assert main(complete_argv) != 0
    captured = capsys.readouterr()
    assert error in captured.err
    assert "Conversation completed." not in captured.out


def test_cli_requires_characters_and_topic(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) != 0
    assert "required" in capsys.readouterr().err
