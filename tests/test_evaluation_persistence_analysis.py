"""Artifact separation, responses, and analysis tests."""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from multi_agent_personalities.evaluation.analysis import analyze_pilot
from multi_agent_personalities.evaluation.persistence import append_response, load_jsonl, save_pilot
from multi_agent_personalities.models import EvaluationTrial, PublicEvaluationTrial, RaterResponse, TrialAnswer


def trials() -> list[EvaluationTrial]:
    return [EvaluationTrial(trial_id=f"trial_{i}", source_run_id="run_1", source_message_id=f"message_{i}", condition="mock", display_text=f"Long anonymized message content number {i}.", candidate_character_ids=("sherlock_holmes", "hercule_poirot"), correct_character_id="sherlock_holmes" if i == 0 else "hercule_poirot", source_provider="mock", synthetic_data=True) for i in range(2)]


def test_pilot_artifacts_separate_answers_and_prevent_duplicate_response(tmp_path: Path) -> None:
    items = trials()
    manifest = {"pilot_id": "pilot_1", "source_run_ids": ["run_1"], "trial_count": 2, "trial_generation": {"duplicate_text_warnings": []}}
    directory = save_pilot(output_root=tmp_path, pilot_id="pilot_1", trials=items, manifest=manifest)
    public_text = (directory / "trials_public.jsonl").read_text()
    assert "correct_character_id" not in public_text
    assert "correct_character_id" in (directory / "answer_key.jsonl").read_text()
    response = RaterResponse(response_id="response_1", trial_id="trial_0", rater_id="rater_1", selected_character_id="sherlock_holmes", confidence=5, timestamp=datetime.now(timezone.utc))
    append_response(directory, response)
    with pytest.raises(ValueError, match="already answered"):
        append_response(directory, response.model_copy(update={"response_id": "response_2"}))
    assert load_jsonl(directory / "responses.jsonl", RaterResponse) == [response]
    with pytest.raises(FileExistsError):
        save_pilot(output_root=tmp_path, pilot_id="pilot_1", trials=items, manifest=manifest)


def test_analysis_known_confusion_and_empty_behavior() -> None:
    internal = trials()
    public = [PublicEvaluationTrial.model_validate(item.public_dict()) for item in internal]
    answers = [TrialAnswer(trial_id=item.trial_id, correct_character_id=item.correct_character_id) for item in internal]
    empty = analyze_pilot(public, answers, [])
    assert empty["overall_accuracy"] is None
    assert empty["confidence_interval"]["lower"] is None
    responses = [RaterResponse(response_id="r1", trial_id="trial_0", rater_id="rater", selected_character_id="sherlock_holmes", confidence=5, timestamp=datetime.now(timezone.utc)), RaterResponse(response_id="r2", trial_id="trial_1", rater_id="rater", selected_character_id="sherlock_holmes", confidence=2, timestamp=datetime.now(timezone.utc))]
    result = analyze_pilot(public, answers, responses)
    assert result["overall_accuracy"] == .5
    assert result["confusion_matrix"]["matrix"]["hercule_poirot"]["sherlock_holmes"] == 1
    assert result["mean_confidence_correct"] == 5
    assert result["mean_confidence_incorrect"] == 2
    assert 0 < result["confidence_interval"]["lower"] < result["confidence_interval"]["upper"] < 1
