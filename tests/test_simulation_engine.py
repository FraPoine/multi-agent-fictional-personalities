"""Tests for the deterministic round-robin simulation engine."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models.persona import Persona
from multi_agent_personalities.simulation import simulate_chat

FIXED_TIME = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)


class RecordingProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, task_name: str) -> str:
        self.prompts.append(prompt)
        return f"Reply {len(self.prompts) - 1}"


def persona(character_id: str, name: str) -> Persona:
    return Persona(
        character_id=character_id,
        display_name=name,
        description=f"Description of {name}.",
        speaking_style=["Precise"],
        reasoning_style=["Methodical"],
        personality_traits=["Observant"],
        behavior_rules=["Address the topic"],
        example_messages=["An example."],
    )


@pytest.fixture
def personas() -> list[Persona]:
    return [persona("sherlock", "Sherlock"), persona("poirot", "Poirot"), persona("l", "L")]


def simulate(personas: list[Persona], provider: RecordingProvider, **overrides: object):
    arguments: dict[str, object] = dict(
        personas=personas,
        topic="A locked-room mystery",
        turn_count=6,
        provider=provider,
        provider_name="recording",
        seed=42,
        model_name="fake-v1",
        run_id="run_fixed",
        timestamp=FIXED_TIME,
    )
    arguments.update(overrides)
    return simulate_chat(**arguments)  # type: ignore[arg-type]


def test_two_personas_alternate_once_per_turn(personas: list[Persona]) -> None:
    provider = RecordingProvider()
    run = simulate(personas[:2], provider)
    assert [message.speaker_character_id for message in run.messages] == [
        "sherlock", "poirot", "sherlock", "poirot", "sherlock", "poirot"
    ]
    assert len(run.messages) == len(provider.prompts) == 6


def test_three_personas_rotate_with_correct_names(personas: list[Persona]) -> None:
    run = simulate(personas, RecordingProvider())
    assert [message.speaker_character_id for message in run.messages] == [
        "sherlock", "poirot", "l", "sherlock", "poirot", "l"
    ]
    assert [message.speaker_name for message in run.messages] == [
        "Sherlock", "Poirot", "L", "Sherlock", "Poirot", "L"
    ]


def test_every_turn_receives_complete_ordered_history(personas: list[Persona]) -> None:
    provider = RecordingProvider()
    simulate(personas[:2], provider, turn_count=4)
    assert "No previous messages." in provider.prompts[0]
    for turn, prompt in enumerate(provider.prompts):
        positions = [prompt.index(f"Reply {prior}") for prior in range(turn)]
        assert positions == sorted(positions)
        assert len(positions) == turn


def test_completed_run_and_messages_have_consistent_metadata(personas: list[Persona]) -> None:
    run = simulate(personas[:2], RecordingProvider(), turn_count=4)
    assert run.status == "completed"
    assert run.character_ids == ("sherlock", "poirot")
    assert run.seed == 42
    assert run.created_at == FIXED_TIME
    assert [message.run_id for message in run.messages] == ["run_fixed"] * 4
    assert [message.turn_index for message in run.messages] == list(range(4))
    assert [message.message_id for message in run.messages] == [
        f"run_fixed_message_{turn:04d}" for turn in range(4)
    ]


def test_result_and_contained_messages_are_immutable(personas: list[Persona]) -> None:
    run = simulate(personas[:2], RecordingProvider(), turn_count=1)
    with pytest.raises(ValidationError):
        run.status = "failed"
    with pytest.raises(ValidationError):
        run.messages[0].text = "Changed"


@pytest.mark.parametrize(
    ("selection", "overrides", "error"),
    [
        (slice(0, 1), {}, "at least two personas"),
        (None, {"topic": " "}, "topic must not be empty"),
        (None, {"provider_name": " "}, "provider_name must not be empty"),
        (None, {"turn_count": 0}, "turn_count must be greater"),
        (None, {"run_id": ""}, "run_id must not be empty"),
        (None, {"timestamp": datetime(2026, 8, 3)}, "timezone-aware"),
    ],
)
def test_invalid_inputs_fail_before_provider_call(personas, selection, overrides, error) -> None:
    provider = RecordingProvider()
    selected = personas[:2] if selection is None else personas[selection]
    with pytest.raises(ValueError, match=error):
        simulate(selected, provider, **overrides)
    assert provider.prompts == []


def test_duplicate_personas_are_rejected(personas: list[Persona]) -> None:
    provider = RecordingProvider()
    with pytest.raises(ValueError, match="unique character_id"):
        simulate([personas[0], personas[0]], provider)
    assert provider.prompts == []


def test_provider_exception_is_propagated(personas: list[Persona]) -> None:
    class FailingProvider:
        def generate(self, prompt: str, *, task_name: str) -> str:
            raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        simulate_chat(
            personas=personas[:2], topic="Mystery", turn_count=2,
            provider=FailingProvider(), provider_name="failing", seed=1,
            run_id="run_fixed", timestamp=FIXED_TIME,
        )
