"""Tests for single-turn agent reply generation."""

from datetime import datetime, timezone

import pytest

from multi_agent_personalities.agent_runtime import generate_reply
from multi_agent_personalities.models.message import Message
from multi_agent_personalities.models.persona import Persona


FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


class SpyProvider:
    """Record deterministic provider calls for runtime assertions."""

    def __init__(self, response: object = "The facts suggest one answer.") -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def generate(self, prompt: str, *, task_name: str) -> str:
        self.calls.append((prompt, task_name))
        return self.response  # type: ignore[return-value]


@pytest.fixture
def sherlock() -> Persona:
    return Persona(
        character_id="sherlock_holmes",
        display_name="Sherlock Holmes",
        description="A consulting detective guided by evidence.",
        speaking_style=["Concise and analytical"],
        reasoning_style=["Separates observation from deduction"],
        personality_traits=["Observant"],
        behavior_rules=["Do not invent evidence"],
        example_messages=["The detail is elementary, once observed."],
    )


def make_message(
    *,
    turn_index: int,
    speaker_name: str,
    text: str,
    run_id: str = "run_001",
) -> Message:
    return Message(
        message_id=f"old_{turn_index}",
        run_id=run_id,
        turn_index=turn_index,
        speaker_character_id=speaker_name.lower().replace(" ", "_"),
        speaker_name=speaker_name,
        text=text,
        provider="mock",
        model="mock-v1",
        timestamp=FIXED_TIME,
        error=None,
    )


def call_runtime(
    sherlock: Persona,
    provider: SpyProvider,
    **overrides: object,
) -> Message:
    arguments: dict[str, object] = {
        "persona": sherlock,
        "history": [],
        "topic": "How should we investigate the locked room?",
        "run_id": "run_001",
        "turn_index": 0,
        "provider": provider,
        "provider_name": "mock",
        "model_name": "mock-v1",
        "timestamp": FIXED_TIME,
    }
    arguments.update(overrides)
    return generate_reply(**arguments)  # type: ignore[arg-type]


def test_valid_call_returns_expected_message_and_calls_provider_once(
    sherlock: Persona,
) -> None:
    provider = SpyProvider("Examine the window before forming a theory.")

    message = call_runtime(sherlock, provider)

    assert isinstance(message, Message)
    assert message.message_id == "run_001_message_0000"
    assert message.run_id == "run_001"
    assert message.turn_index == 0
    assert message.speaker_character_id == "sherlock_holmes"
    assert message.speaker_name == "Sherlock Holmes"
    assert message.provider == "mock"
    assert message.model == "mock-v1"
    assert message.text == "Examine the window before forming a theory."
    assert message.timestamp == FIXED_TIME
    assert message.error is None
    assert len(provider.calls) == 1
    assert provider.calls[0][1] == "agent_reply"


def test_prompt_contains_persona_topic_and_ordered_history(
    sherlock: Persona,
) -> None:
    provider = SpyProvider()
    first_text = "We should inspect the window."
    second_text = "The intruder's motive matters as well."
    history = [
        make_message(
            turn_index=0,
            speaker_name="Sherlock Holmes",
            text=first_text,
        ),
        make_message(
            turn_index=1,
            speaker_name="Hercule Poirot",
            text=second_text,
        ),
    ]

    call_runtime(
        sherlock,
        provider,
        history=history,
        turn_index=2,
    )

    prompt = provider.calls[0][0]
    assert "Sherlock Holmes" in prompt
    assert sherlock.description in prompt
    assert "How should we investigate the locked room?" in prompt
    assert "[Turn 0] Sherlock Holmes" in prompt
    assert "[Turn 1] Hercule Poirot" in prompt
    assert first_text in prompt
    assert second_text in prompt
    assert prompt.index(first_text) < prompt.index(second_text)
    assert "Produce only the next chat message." in prompt


def test_empty_history_is_explicit_and_input_is_not_mutated(
    sherlock: Persona,
) -> None:
    provider = SpyProvider()
    history: list[Message] = []

    call_runtime(sherlock, provider, history=history)

    assert history == []
    assert "No previous messages." in provider.calls[0][0]


def test_non_empty_history_is_not_mutated(sherlock: Persona) -> None:
    provider = SpyProvider()
    history = [
        make_message(turn_index=0, speaker_name="Hercule Poirot", text="Order.")
    ]
    original = history.copy()

    call_runtime(sherlock, provider, history=history, turn_index=1)

    assert history == original


def test_complete_history_is_accepted_for_later_turn(
    sherlock: Persona,
) -> None:
    provider = SpyProvider()
    history = [
        make_message(turn_index=0, speaker_name="Sherlock Holmes", text="Facts."),
        make_message(turn_index=1, speaker_name="Hercule Poirot", text="Order."),
    ]

    message = call_runtime(
        sherlock,
        provider,
        history=history,
        turn_index=2,
    )

    assert message.turn_index == 2
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"topic": " \t "}, "topic must not be empty"),
        ({"run_id": ""}, "run_id must not be empty"),
        ({"provider_name": " "}, "provider_name must not be empty"),
        ({"turn_index": -1}, "turn_index must be greater"),
    ],
)
def test_invalid_scalar_inputs_are_rejected_before_provider_call(
    sherlock: Persona,
    overrides: dict[str, object],
    error: str,
) -> None:
    provider = SpyProvider()

    with pytest.raises(ValueError, match=error):
        call_runtime(sherlock, provider, **overrides)

    assert provider.calls == []


def test_history_from_another_run_is_rejected(sherlock: Persona) -> None:
    provider = SpyProvider()
    history = [
        make_message(
            turn_index=0,
            speaker_name="Hercule Poirot",
            text="Order.",
            run_id="another_run",
        )
    ]

    with pytest.raises(ValueError, match="requested run_id"):
        call_runtime(sherlock, provider, history=history, turn_index=1)


def test_out_of_order_history_is_rejected(sherlock: Persona) -> None:
    provider = SpyProvider()
    history = [
        make_message(
            turn_index=1,
            speaker_name="Hercule Poirot",
            text="Order.",
        ),
        make_message(
            turn_index=0,
            speaker_name="Sherlock Holmes",
            text="Facts.",
        ),
    ]

    with pytest.raises(ValueError, match="chronological order"):
        call_runtime(sherlock, provider, history=history, turn_index=2)


def test_history_with_missing_middle_turn_is_rejected(
    sherlock: Persona,
) -> None:
    provider = SpyProvider()
    history = [
        make_message(turn_index=0, speaker_name="Sherlock Holmes", text="Facts."),
        make_message(turn_index=2, speaker_name="Hercule Poirot", text="Order."),
    ]

    with pytest.raises(ValueError, match="every previous turn"):
        call_runtime(sherlock, provider, history=history, turn_index=3)


def test_incomplete_history_is_rejected(sherlock: Persona) -> None:
    provider = SpyProvider()
    history = [
        make_message(turn_index=0, speaker_name="Sherlock Holmes", text="Facts.")
    ]

    with pytest.raises(ValueError, match="every previous turn"):
        call_runtime(sherlock, provider, history=history, turn_index=2)


def test_future_history_turn_is_rejected(sherlock: Persona) -> None:
    provider = SpyProvider()
    history = [
        make_message(turn_index=0, speaker_name="Sherlock Holmes", text="Facts."),
        make_message(turn_index=2, speaker_name="Hercule Poirot", text="Order."),
    ]

    with pytest.raises(ValueError, match="chronological order"):
        call_runtime(sherlock, provider, history=history, turn_index=2)


def test_duplicate_history_turn_indexes_are_rejected(
    sherlock: Persona,
) -> None:
    provider = SpyProvider()
    history = [
        make_message(turn_index=0, speaker_name="Sherlock Holmes", text="Facts."),
        make_message(turn_index=0, speaker_name="Hercule Poirot", text="Order."),
    ]

    with pytest.raises(ValueError, match="duplicate turn indexes"):
        call_runtime(sherlock, provider, history=history, turn_index=1)


@pytest.mark.parametrize("response", ["", " \n\t", None, 42])
def test_invalid_provider_response_is_rejected(
    sherlock: Persona,
    response: object,
) -> None:
    provider = SpyProvider(response)

    with pytest.raises(ValueError, match="non-empty string"):
        call_runtime(sherlock, provider)

    assert len(provider.calls) == 1


def test_provider_exception_is_not_swallowed(sherlock: Persona) -> None:
    class FailingProvider:
        def generate(self, prompt: str, *, task_name: str) -> str:
            raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        generate_reply(
            persona=sherlock,
            history=[],
            topic="A mystery",
            run_id="run_001",
            turn_index=0,
            provider=FailingProvider(),
            provider_name="mock",
        )


def test_naive_timestamp_is_rejected_before_provider_call(
    sherlock: Persona,
) -> None:
    provider = SpyProvider()

    with pytest.raises(ValueError, match="timezone-aware"):
        call_runtime(
            sherlock,
            provider,
            timestamp=datetime(2026, 7, 30, 12, 0),
        )

    assert provider.calls == []


def test_supplied_aware_timestamp_is_preserved(sherlock: Persona) -> None:
    provider = SpyProvider()
    timestamp = datetime(
        2026,
        7,
        30,
        14,
        0,
        tzinfo=timezone.utc,
    )

    message = call_runtime(sherlock, provider, timestamp=timestamp)

    assert message.timestamp is timestamp
