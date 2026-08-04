"""Network-free end-to-end technical pilot preparation."""

import json
from pathlib import Path
import socket

import pytest

from multi_agent_personalities.application.evaluation_service import prepare_technical_pilot


ROOT = Path(__file__).resolve().parents[1]


def test_prepares_three_runs_six_balanced_trials_without_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    result = prepare_technical_pilot(output_root=tmp_path, project_root=ROOT, config_path=ROOT / "configs/evaluation_pilot.yaml", pilot_id="pilot_e2e")
    assert len(result.source_run_ids) == 3
    assert len((result.pilot_directory / "trials_public.jsonl").read_text().splitlines()) == 6
    assert len((result.pilot_directory / "answer_key.jsonl").read_text().splitlines()) == 6
    assert (result.pilot_directory / "responses.jsonl").read_text() == ""
    manifest = json.loads((result.pilot_directory / "pilot_manifest.json").read_text())
    assert manifest["trial_generation"]["accepted_trials_per_character"] == {"hercule_poirot": 3, "sherlock_holmes": 3}
    assert len(manifest["trial_generation"]["duplicate_text_warnings"]) == 2
    for run_id in result.source_run_ids:
        assert (tmp_path / "conversations" / "runs" / run_id / "run.json").is_file()
