"""Artifact separation, responses, and analysis tests."""

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import pytest

from multi_agent_personalities.evaluation.analysis import analyze_pilot
import multi_agent_personalities.evaluation.persistence as persistence
from multi_agent_personalities.evaluation.persistence import load_jsonl, save_pilot, save_synthetic_responses, submit_rater_response
from multi_agent_personalities.models import EvaluationTrial, PublicEvaluationTrial, RaterResponse, TrialAnswer


def trials() -> list[EvaluationTrial]:
    return [EvaluationTrial(trial_id=f"trial_{i}", source_run_id="run_1", source_message_id=f"message_{i}", condition="mock", display_text=f"Long anonymized message content number {i}.", candidate_character_ids=("sherlock_holmes", "hercule_poirot"), correct_character_id="sherlock_holmes" if i == 0 else "hercule_poirot", source_provider="mock", synthetic_data=True) for i in range(2)]


def test_pilot_artifacts_separate_answers_and_prevent_duplicate_response(tmp_path: Path) -> None:
    items = trials()
    manifest = {"pilot_id": "pilot_1", "source_run_ids": ["run_1"], "trial_count": 2, "trial_generation": {"duplicate_text_warnings": []}}
    directory = save_pilot(output_root=tmp_path, pilot_id="pilot_1", trials=items, manifest=manifest)
    public_text = (directory / "trials_public.jsonl").read_text()
    assert "correct_character_id" not in public_text
    assert "source_run_id" not in public_text
    assert "source_message_id" not in public_text
    assert "message_0" not in public_text
    assert "correct_character_id" in (directory / "answer_key.jsonl").read_text()
    response = RaterResponse(response_id="response_1", trial_id="trial_0", rater_id="rater_1", selected_character_id="sherlock_holmes", confidence=5, timestamp=datetime.now(timezone.utc))
    submit_rater_response(directory, response)
    with pytest.raises(ValueError, match="duplicated response"):
        submit_rater_response(directory, response.model_copy(update={"response_id": "response_2"}))
    assert load_jsonl(directory / "responses.jsonl", RaterResponse) == [response]
    assert (directory / "synthetic_responses.jsonl").read_text() == ""
    with pytest.raises(FileExistsError):
        save_pilot(output_root=tmp_path, pilot_id="pilot_1", trials=items, manifest=manifest)


def test_analysis_known_confusion_and_empty_behavior() -> None:
    internal = trials()
    public = [PublicEvaluationTrial.model_validate(item.public_dict()) for item in internal]
    answers = [TrialAnswer(trial_id=item.trial_id, correct_character_id=item.correct_character_id, source_run_id=item.source_run_id, source_message_id=item.source_message_id) for item in internal]
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


def test_synthetic_responses_are_separate_and_manifest_is_accurate(tmp_path: Path) -> None:
    items = trials()
    manifest = {"pilot_id": "pilot_synthetic", "source_run_ids": ["run_1"], "trial_count": 2, "synthetic_responses_created": False, "trial_generation": {"duplicate_text_warnings": []}}
    directory = save_pilot(output_root=tmp_path, pilot_id="pilot_synthetic", trials=items, manifest=manifest)
    responses = [RaterResponse(response_id=f"synthetic_{index}", trial_id=item.trial_id, rater_id="synthetic_rater", selected_character_id=item.correct_character_id, confidence=3, timestamp=datetime.now(timezone.utc), synthetic_data=True) for index, item in enumerate(items)]
    result = save_synthetic_responses(directory, responses)
    assert result["response_source"] == "synthetic"
    assert result["total_response_count"] == 2
    assert (directory / "responses.jsonl").read_text() == ""
    assert len((directory / "synthetic_responses.jsonl").read_text().splitlines()) == 2
    assert json.loads((directory / "pilot_manifest.json").read_text())["synthetic_responses_created"] is True
    human = persistence.refresh_analysis(directory)
    assert human["response_source"] == "human"
    assert human["total_response_count"] == 0


def test_analysis_rejects_mixed_sources_and_duplicate_response_ids() -> None:
    internal = trials()
    public = [PublicEvaluationTrial.model_validate(item.public_dict()) for item in internal]
    answers = [TrialAnswer(trial_id=item.trial_id, correct_character_id=item.correct_character_id, source_run_id=item.source_run_id, source_message_id=item.source_message_id) for item in internal]
    human = RaterResponse(response_id="same", trial_id="trial_0", rater_id="rater_1", selected_character_id="sherlock_holmes", confidence=3, timestamp=datetime.now(timezone.utc))
    synthetic = RaterResponse(response_id="other", trial_id="trial_1", rater_id="synthetic_1", selected_character_id="hercule_poirot", confidence=3, timestamp=datetime.now(timezone.utc), synthetic_data=True)
    with pytest.raises(ValueError, match="response source"):
        analyze_pilot(public, answers, [human, synthetic])
    with pytest.raises(ValueError, match="response ID"):
        analyze_pilot(public, answers, [human, human.model_copy(update={"trial_id": "trial_1", "rater_id": "rater_2"})])


def test_response_ids_are_unique_across_human_and_synthetic_files(tmp_path: Path) -> None:
    items = trials()
    manifest = {"pilot_id": "pilot_global_ids", "source_run_ids": ["run_1"], "trial_count": 2, "synthetic_responses_created": False, "trial_generation": {"duplicate_text_warnings": []}}
    directory = save_pilot(output_root=tmp_path, pilot_id="pilot_global_ids", trials=items, manifest=manifest)
    human = RaterResponse(response_id="global_id", trial_id="trial_0", rater_id="rater", selected_character_id="sherlock_holmes", confidence=3, timestamp=datetime.now(timezone.utc))
    submit_rater_response(directory, human)
    synthetic = RaterResponse(response_id="global_id", trial_id="trial_1", rater_id="synthetic", selected_character_id="hercule_poirot", confidence=3, timestamp=datetime.now(timezone.utc), synthetic_data=True)
    with pytest.raises(ValueError, match="across response files"):
        save_synthetic_responses(directory, [synthetic])


def test_concurrent_submissions_keep_analysis_consistent(tmp_path: Path) -> None:
    items = trials()
    manifest = {"pilot_id": "pilot_concurrent", "source_run_ids": ["run_1"], "trial_count": 2, "trial_generation": {"duplicate_text_warnings": []}}
    directory = save_pilot(output_root=tmp_path, pilot_id="pilot_concurrent", trials=items, manifest=manifest)
    responses = [RaterResponse(response_id=f"response_{index}", trial_id=item.trial_id, rater_id=f"rater_{index}", selected_character_id=item.correct_character_id, confidence=4, timestamp=datetime.now(timezone.utc)) for index, item in enumerate(items)]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda response: submit_rater_response(directory, response), responses))
    persisted = load_jsonl(directory / "responses.jsonl", RaterResponse)
    analysis = json.loads((directory / "analysis.json").read_text())
    assert {item.response_id for item in persisted} == {"response_0", "response_1"}
    assert analysis["total_response_count"] == 2
    assert max(item["total_response_count"] for item in results) == 2


def test_failed_submission_never_writes_partial_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    items = trials()
    manifest = {"pilot_id": "pilot_failure", "source_run_ids": ["run_1"], "trial_count": 2, "trial_generation": {"duplicate_text_warnings": []}}
    directory = save_pilot(output_root=tmp_path, pilot_id="pilot_failure", trials=items, manifest=manifest)
    response = RaterResponse(response_id="response_1", trial_id="trial_0", rater_id="rater_1", selected_character_id="sherlock_holmes", confidence=4, timestamp=datetime.now(timezone.utc))
    real_replace = persistence._replace_text
    def fail_response(path: Path, content: str) -> None:
        if path.name == "responses.jsonl":
            raise OSError("injected failure")
        real_replace(path, content)
    monkeypatch.setattr(persistence, "_replace_text", fail_response)
    with pytest.raises(OSError, match="injected"):
        submit_rater_response(directory, response)
    assert (directory / "responses.jsonl").read_text() == ""


@pytest.mark.parametrize(
    ("artifact", "replacement", "message"),
    [
        ("trials_public.jsonl", lambda line: line + line, "duplicated public trial"),
        ("answer_key.jsonl", lambda line: line + line, "duplicated private"),
        ("answer_key.jsonl", lambda line: "", "do not match"),
        ("responses.jsonl", lambda line: "{broken json}\n", "malformed"),
    ],
)
def test_integrity_failures_are_loud(
    tmp_path: Path, artifact: str, replacement: object, message: str
) -> None:
    items = trials()
    manifest = {"pilot_id": "pilot_integrity", "source_run_ids": ["run_1"], "trial_count": 2, "trial_generation": {"duplicate_text_warnings": []}}
    directory = save_pilot(output_root=tmp_path, pilot_id="pilot_integrity", trials=items, manifest=manifest)
    path = directory / artifact
    original = path.read_text()
    first_line = original.splitlines(keepends=True)[0] if original else ""
    path.write_text(replacement(first_line))
    with pytest.raises(ValueError, match=message):
        persistence.refresh_analysis(directory)
