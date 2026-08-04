"""Reproducible descriptive analysis for the technical pilot."""

from collections import Counter
import math
from collections.abc import Sequence

from multi_agent_personalities.models import PublicEvaluationTrial, RaterResponse, TrialAnswer


DISCLAIMER = (
    "This is a technical mock pilot. Synthetic mock messages cannot establish "
    "persona recognizability or support scientific conclusions."
)


def _wilson_interval(correct: int, total: int, z: float = 1.959963984540054) -> tuple[float | None, float | None]:
    if total == 0:
        return None, None
    proportion = correct / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def analyze_pilot(
    trials: Sequence[PublicEvaluationTrial], answers: Sequence[TrialAnswer],
    responses: Sequence[RaterResponse],
) -> dict[str, object]:
    """Validate linked records and compute fixed pilot metrics."""
    trial_map = {trial.trial_id: trial for trial in trials}
    if len(trial_map) != len(trials):
        raise ValueError("duplicated trial IDs")
    answer_map = {answer.trial_id: answer.correct_character_id for answer in answers}
    if len(answer_map) != len(answers):
        raise ValueError("duplicated answer-key trial IDs")
    if set(answer_map) != set(trial_map):
        raise ValueError("answer key must contain exactly one answer for every trial")
    seen: set[tuple[str, str]] = set()
    for response in responses:
        if response.trial_id not in trial_map:
            raise ValueError(f"unknown trial ID: {response.trial_id}")
        if response.selected_character_id not in trial_map[response.trial_id].candidate_character_ids:
            raise ValueError("response selection is not supported by its trial")
        key = (response.rater_id, response.trial_id)
        if key in seen:
            raise ValueError("duplicated response for rater and trial")
        seen.add(key)

    correct_flags = [answer_map[item.trial_id] == item.selected_character_id for item in responses]
    correct = sum(correct_flags)
    total = len(responses)
    low, high = _wilson_interval(correct, total)
    character_ids = ("sherlock_holmes", "hercule_poirot")
    per_character: dict[str, dict[str, object]] = {}
    confusion = {truth: {selected: 0 for selected in character_ids} for truth in character_ids}
    correct_confidence: list[int] = []
    incorrect_confidence: list[int] = []
    for response, is_correct in zip(responses, correct_flags):
        truth = answer_map[response.trial_id]
        confusion[truth][response.selected_character_id] += 1
        (correct_confidence if is_correct else incorrect_confidence).append(response.confidence)
    for character_id in character_ids:
        matching = [response for response in responses if answer_map[response.trial_id] == character_id]
        count_correct = sum(response.selected_character_id == character_id for response in matching)
        per_character[character_id] = {
            "responses": len(matching),
            "correct": count_correct,
            "accuracy": count_correct / len(matching) if matching else None,
        }
    mean = lambda values: sum(values) / len(values) if values else None
    return {
        "disclaimer": DISCLAIMER,
        "synthetic_response_count": sum(item.synthetic_data for item in responses),
        "total_response_count": total,
        "correct_response_count": correct,
        "overall_accuracy": correct / total if total else None,
        "chance_baseline": 0.50,
        "confidence_interval": {"method": "Wilson score", "level": 0.95, "lower": low, "upper": high},
        "per_character_accuracy": per_character,
        "confusion_matrix": {"rows_are_true": True, "matrix": confusion},
        "mean_confidence_correct": mean(correct_confidence),
        "mean_confidence_incorrect": mean(incorrect_confidence),
        "response_count_per_rater": dict(sorted(Counter(item.rater_id for item in responses).items())),
    }
