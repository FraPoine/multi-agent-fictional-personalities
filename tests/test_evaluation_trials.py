"""Filtering and deterministic trial generation tests."""

from datetime import datetime, timezone
import pytest

from multi_agent_personalities.evaluation.trials import build_trials
from multi_agent_personalities.models import ConversationRun, Message


NOW = datetime(2026, 8, 4, tzinfo=timezone.utc)


def run_with_texts(run_id: str, texts: list[tuple[str, str]]) -> ConversationRun:
    messages = tuple(Message(message_id=f"{run_id}_message_{i}", run_id=run_id, turn_index=i, speaker_character_id=character, speaker_name="Hidden Name", text=text, provider="mock", model="mock", timestamp=NOW) for i, (character, text) in enumerate(texts))
    return ConversationRun(run_id=run_id, topic="Neutral topic", character_ids=("sherlock_holmes", "hercule_poirot"), turn_count=len(messages), seed=42, provider="mock", created_at=NOW, status="completed", messages=messages)


def test_trials_are_balanced_stable_and_deterministic() -> None:
    texts = [(character, f"A sufficiently detailed neutral statement number {index} about evidence.") for index in range(8) for character in ("sherlock_holmes", "hercule_poirot")]
    run = run_with_texts("run_one", texts)
    first = build_trials([run])
    second = build_trials([run])
    assert first == second
    assert len(first.trials) == 6
    assert {item.trial_id for item in first.trials} == {item.trial_id for item in second.trials}
    assert first.summary["accepted_trials_per_character"] == {"hercule_poirot": 3, "sherlock_holmes": 3}
    assert [item.candidate_character_ids for item in first.trials] == [item.candidate_character_ids for item in second.trials]


def test_filter_records_identity_empty_short_and_malformed_reasons() -> None:
    valid = [(character, f"This anonymous evidence statement is safely long number {index}.") for index in range(3) for character in ("sherlock_holmes", "hercule_poirot")]
    extras = [("sherlock_holmes", "Holmes noticed this."), ("hercule_poirot", "short")]
    run = run_with_texts("run_filter", valid + extras)
    result = build_trials([run])
    assert result.summary["excluded_messages"] == 2
    assert result.summary["exclusions_by_reason"] == {"below_minimum_length": 1, "identity_leakage": 1}


def test_balanced_sample_fails_loudly_when_short() -> None:
    run = run_with_texts("run_short", [("sherlock_holmes", "A long enough neutral statement for this test only.")] * 3 + [("hercule_poirot", "Only one sufficiently detailed neutral statement.")])
    with pytest.raises(ValueError, match="balanced"):
        build_trials([run])
