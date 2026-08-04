"""Validation tests for blind-evaluation domain models."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from multi_agent_personalities.models import EvaluationTrial, RaterResponse


def make_trial() -> EvaluationTrial:
    return EvaluationTrial(trial_id="trial_1", source_run_id="run_1", source_message_id="message_1", condition="persona_seeded_mock", display_text="A sufficiently long anonymous investigation statement.", candidate_character_ids=("sherlock_holmes", "hercule_poirot"), correct_character_id="sherlock_holmes", source_provider="mock", synthetic_data=True)


def test_trial_is_immutable_and_public_form_has_no_answer() -> None:
    trial = make_trial()
    assert "correct_character_id" not in trial.public_dict()
    with pytest.raises(ValidationError):
        trial.display_text = "changed"


@pytest.mark.parametrize("confidence", [0, 6])
def test_response_rejects_confidence_outside_scale(confidence: int) -> None:
    with pytest.raises(ValidationError):
        RaterResponse(response_id="response_1", trial_id="trial_1", rater_id="rater_1", selected_character_id="sherlock_holmes", confidence=confidence, timestamp=datetime.now(timezone.utc))


def test_response_rejects_unknown_character() -> None:
    with pytest.raises(ValidationError):
        RaterResponse(response_id="response_1", trial_id="trial_1", rater_id="rater_1", selected_character_id="unknown", confidence=3, timestamp=datetime.now(timezone.utc))
