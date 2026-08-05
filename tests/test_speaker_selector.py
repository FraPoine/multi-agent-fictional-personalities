"""Isolated tests for speaker-selection contracts and round-robin behavior."""

from collections.abc import Sequence
from datetime import datetime, timezone

import pytest

from multi_agent_personalities.models import Message
from multi_agent_personalities.simulation import (
    RoundRobinSelector,
    SpeakerSelector,
    select_valid_speaker,
)


def select(
    participant_ids: list[str],
    turn_index: int,
    history: list[Message] | None = None,
) -> str:
    return RoundRobinSelector().select_next(
        participant_ids=participant_ids,
        history=[] if history is None else history,
        turn_index=turn_index,
    )


@pytest.mark.parametrize(
    ("participant_ids", "turns", "expected"),
    [
        (
            ["alpha", "beta"],
            range(4),
            ["alpha", "beta", "alpha", "beta"],
        ),
        (
            ["alpha", "beta", "gamma"],
            range(5),
            ["alpha", "beta", "gamma", "alpha", "beta"],
        ),
        (
            ["alpha", "beta", "gamma", "delta"],
            range(8),
            [
                "alpha", "beta", "gamma", "delta",
                "alpha", "beta", "gamma", "delta",
            ],
        ),
    ],
)
def test_round_robin_preserves_order_for_multiple_participant_counts(
    participant_ids: list[str],
    turns: range,
    expected: list[str],
) -> None:
    assert [select(participant_ids, turn) for turn in turns] == expected


def test_large_turn_index_uses_direct_modular_selection() -> None:
    participant_ids = ["alpha", "beta", "gamma"]

    assert select(participant_ids, 10_000) == participant_ids[10_000 % 3]


def test_single_participant_is_supported_by_low_level_selector() -> None:
    assert select(["alpha"], 0) == "alpha"
    assert select(["alpha"], 10_000) == "alpha"


@pytest.mark.parametrize(
    ("participant_ids", "turn_index", "error"),
    [
        ([], 0, "at least one participant"),
        (["alpha", "beta", "alpha"], 0, "must not contain duplicates"),
        (["alpha", "beta"], -1, "greater than or equal to zero"),
    ],
)
def test_invalid_selection_inputs_fail_clearly(
    participant_ids: list[str],
    turn_index: int,
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        select(participant_ids, turn_index)


def test_repeated_calls_are_deterministic_without_internal_counter() -> None:
    selector = RoundRobinSelector()
    arguments = {
        "participant_ids": ["alpha", "beta", "gamma"],
        "history": [],
        "turn_index": 4,
    }

    assert [selector.select_next(**arguments) for _ in range(5)] == ["beta"] * 5


def test_participant_sequence_is_not_mutated() -> None:
    participant_ids = ["gamma", "alpha", "beta"]
    before = participant_ids.copy()

    assert select(participant_ids, 4) == "alpha"
    assert participant_ids == before


def message(turn_index: int, speaker: str) -> Message:
    return Message(
        message_id=f"message-{turn_index}",
        run_id="selector-test-run",
        turn_index=turn_index,
        speaker_character_id=speaker,
        speaker_name=speaker.title(),
        text=f"History message {turn_index}.",
        provider="test",
        model=None,
        timestamp=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
        error=None,
    )


def test_history_is_not_mutated() -> None:
    history = [message(0, "alpha"), message(1, "beta")]
    before = tuple(history)

    assert select(["alpha", "beta"], 2, history) == "alpha"
    assert tuple(history) == before
    assert all(current is original for current, original in zip(history, before))


def test_round_robin_is_independent_of_history_content() -> None:
    participant_ids = ["alpha", "beta", "gamma"]
    short_history = [message(0, "alpha")]
    different_history = [
        message(0, "gamma"),
        message(1, "gamma"),
        message(2, "beta"),
    ]

    assert select(participant_ids, 4, short_history) == "beta"
    assert select(participant_ids, 4, different_history) == "beta"


class UnknownSelector:
    def select_next(
        self,
        *,
        participant_ids: Sequence[str],
        history: Sequence[Message],
        turn_index: int,
    ) -> str:
        return "unknown-agent"


class FixedSelector:
    def select_next(
        self,
        *,
        participant_ids: Sequence[str],
        history: Sequence[Message],
        turn_index: int,
    ) -> str:
        return participant_ids[-1]


def test_invalid_custom_selector_result_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported participant.*unknown-agent"):
        select_valid_speaker(
            UnknownSelector(),
            participant_ids=["alpha", "beta"],
            history=[],
            turn_index=0,
        )


def test_valid_custom_selector_result_is_accepted() -> None:
    assert select_valid_speaker(
        FixedSelector(),
        participant_ids=["alpha", "beta"],
        history=[],
        turn_index=0,
    ) == "beta"


def call_through_protocol(selector: SpeakerSelector) -> str:
    """Exercise structural compatibility without runtime typing dependencies."""

    return selector.select_next(
        participant_ids=["alpha", "beta"],
        history=[],
        turn_index=1,
    )


def test_round_robin_satisfies_speaker_selector_protocol() -> None:
    assert call_through_protocol(RoundRobinSelector()) == "beta"
