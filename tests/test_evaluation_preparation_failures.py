"""Failure-safety tests for technical-pilot preparation."""

from pathlib import Path
from typing import Any

import pytest

from multi_agent_personalities.application.conversation_service import ConversationResult, run_mock_conversation
from multi_agent_personalities.application.evaluation_service import prepare_technical_pilot


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "evaluation_pilot.yaml"


def source_directories(output_root: Path, pilot_id: str) -> list[Path]:
    return [output_root / "conversations" / "runs" / f"{pilot_id}_source_{index}" for index in range(1, 4)]


def test_invalid_external_config_is_rejected_before_generation(tmp_path: Path) -> None:
    external = tmp_path / "external.yaml"
    external.write_text(CONFIG.read_text())
    called = False
    def reject_call(**kwargs: Any) -> object:
        nonlocal called
        called = True
        raise AssertionError("conversation generation must not start")
    with pytest.raises(ValueError, match="project root"):
        prepare_technical_pilot(output_root=tmp_path / "outputs", project_root=ROOT, config_path=external, pilot_id="pilot_external", _run_conversation=reject_call)
    assert called is False


def test_insufficient_messages_cleanup_and_retry(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    def leaking_run(**kwargs: Any) -> ConversationResult:
        result = run_mock_conversation(**kwargs)
        messages = tuple(message.model_copy(update={"text": "Sherlock reveals identity directly."}) for message in result.run.messages)
        return ConversationResult(run=result.run.model_copy(update={"messages": messages}), artifact_directory=result.artifact_directory)
    with pytest.raises(ValueError, match="balanced"):
        prepare_technical_pilot(output_root=output_root, project_root=ROOT, config_path=CONFIG, pilot_id="pilot_retry", _run_conversation=leaking_run)
    assert all(not path.exists() for path in source_directories(output_root, "pilot_retry"))
    result = prepare_technical_pilot(output_root=output_root, project_root=ROOT, config_path=CONFIG, pilot_id="pilot_retry")
    assert result.pilot_directory.is_dir()


def test_pilot_publication_failure_cleans_only_created_runs(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    unrelated = output_root / "conversations" / "runs" / "unrelated"
    unrelated.mkdir(parents=True)
    marker = unrelated / "keep.txt"
    marker.write_text("keep")
    def fail_save(**kwargs: Any) -> Path:
        raise OSError("injected pilot persistence failure")
    with pytest.raises(OSError, match="injected"):
        prepare_technical_pilot(output_root=output_root, project_root=ROOT, config_path=CONFIG, pilot_id="pilot_save_failure", _save_pilot=fail_save)
    assert marker.read_text() == "keep"
    assert all(not path.exists() for path in source_directories(output_root, "pilot_save_failure"))
    assert not (output_root / "evaluation" / "pilots" / "pilot_save_failure").exists()
