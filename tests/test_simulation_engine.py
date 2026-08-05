"""Tests for conversation simulation with participant-owned providers."""

import socket
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models import Persona
from multi_agent_personalities.simulation import (
    ConversationParticipant,
    simulate_chat,
)


FIXED_TIME = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)


class RecordingProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, task_name: str) -> str:
        self.prompts.append(prompt)
        return self.response


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


def participant(character_id: str, name: str) -> ConversationParticipant:
    return ConversationParticipant(
        persona=persona(character_id, name),
        provider=RecordingProvider(f"response-from-{character_id}"),
        provider_name="recording",
        model_name="fake-v1",
    )


@pytest.fixture
def participants() -> list[ConversationParticipant]:
    return [
        participant("alpha", "Alpha"),
        participant("beta", "Beta"),
        participant("gamma", "Gamma"),
    ]


def simulate(
    participants: list[ConversationParticipant],
    **overrides: object,
):
    arguments: dict[str, object] = dict(
        participants=participants,
        topic="A locked-room mystery",
        turn_count=6,
        seed=42,
        run_id="run_fixed",
        timestamp=FIXED_TIME,
    )
    arguments.update(overrides)
    return simulate_chat(**arguments)  # type: ignore[arg-type]


def test_two_participants_preserve_speaker_and_provider_binding(
    participants: list[ConversationParticipant],
) -> None:
    selected = participants[:2]
    run = simulate(selected)

    assert [message.speaker_character_id for message in run.messages] == [
        "alpha", "beta", "alpha", "beta", "alpha", "beta",
    ]
    assert [message.text for message in run.messages] == [
        "response-from-alpha", "response-from-beta",
        "response-from-alpha", "response-from-beta",
        "response-from-alpha", "response-from-beta",
    ]
    assert [len(item.provider.prompts) for item in selected] == [3, 3]  # type: ignore[attr-defined]


def test_reversed_participant_order_keeps_response_ownership(
    participants: list[ConversationParticipant],
) -> None:
    selected = [participants[1], participants[0]]
    run = simulate(selected, turn_count=4)

    assert [message.speaker_character_id for message in run.messages] == [
        "beta", "alpha", "beta", "alpha",
    ]
    assert [message.text for message in run.messages] == [
        "response-from-beta", "response-from-alpha",
        "response-from-beta", "response-from-alpha",
    ]


def test_three_participants_and_partial_round_have_exact_call_counts(
    participants: list[ConversationParticipant],
) -> None:
    run = simulate(participants, turn_count=5)

    assert [message.speaker_character_id for message in run.messages] == [
        "alpha", "beta", "gamma", "alpha", "beta",
    ]
    assert [message.text for message in run.messages] == [
        "response-from-alpha", "response-from-beta", "response-from-gamma",
        "response-from-alpha", "response-from-beta",
    ]
    call_counts = [len(item.provider.prompts) for item in participants]  # type: ignore[attr-defined]
    assert call_counts == [2, 2, 1]
    assert sum(call_counts) == run.turn_count == len(run.messages)


def test_every_turn_receives_complete_ordered_history(
    participants: list[ConversationParticipant],
) -> None:
    run = simulate(participants[:2], turn_count=4)
    prompts_by_turn: list[str] = []
    for message in run.messages:
        bound = next(
            item for item in participants if item.character_id == message.speaker_character_id
        )
        provider = bound.provider
        prompt_index = sum(
            1
            for prior in run.messages[: message.turn_index]
            if prior.speaker_character_id == message.speaker_character_id
        )
        prompts_by_turn.append(provider.prompts[prompt_index])  # type: ignore[attr-defined]

    assert "No previous messages." in prompts_by_turn[0]
    for turn, prompt in enumerate(prompts_by_turn):
        for prior_message in run.messages[:turn]:
            assert prior_message.text in prompt


def test_completed_run_and_messages_have_consistent_metadata(
    participants: list[ConversationParticipant],
) -> None:
    run = simulate(participants[:2], turn_count=4)
    assert run.status == "completed"
    assert run.character_ids == ("alpha", "beta")
    assert run.provider == "recording"
    assert run.model == "fake-v1"
    assert run.seed == 42
    assert run.created_at == FIXED_TIME
    assert [message.run_id for message in run.messages] == ["run_fixed"] * 4
    assert [message.turn_index for message in run.messages] == list(range(4))


def test_result_and_contained_messages_are_immutable(
    participants: list[ConversationParticipant],
) -> None:
    run = simulate(participants[:2], turn_count=1)
    with pytest.raises(ValidationError):
        run.status = "failed"
    with pytest.raises(ValidationError):
        run.messages[0].text = "Changed"


@pytest.mark.parametrize(
    ("selection", "overrides", "error"),
    [
        (slice(0, 1), {}, "at least two participants"),
        (None, {"topic": " "}, "topic must not be empty"),
        (None, {"turn_count": 0}, "turn_count must be greater"),
        (None, {"run_id": ""}, "run_id must not be empty"),
        (None, {"timestamp": datetime(2026, 8, 3)}, "timezone-aware"),
    ],
)
def test_invalid_inputs_fail_before_provider_call(
    participants,
    selection,
    overrides,
    error,
) -> None:
    selected = participants[:2] if selection is None else participants[selection]
    with pytest.raises(ValueError, match=error):
        simulate(selected, **overrides)
    assert all(not item.provider.prompts for item in selected)


def test_duplicate_participant_identity_is_rejected_before_generation(
    participants: list[ConversationParticipant],
) -> None:
    duplicate = replace(participants[1], persona=participants[0].persona)
    selected = [participants[0], duplicate]

    with pytest.raises(ValueError, match="unique character_id"):
        simulate(selected)
    assert all(not item.provider.prompts for item in selected)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("provider_name", "different", "uniform provider_name"),
        ("model_name", "different", "uniform model_name"),
        ("model_name", None, "uniform model_name"),
    ],
)
def test_mixed_run_metadata_fails_before_generation(
    participants: list[ConversationParticipant],
    field: str,
    value: object,
    error: str,
) -> None:
    selected = [participants[0], replace(participants[1], **{field: value})]

    with pytest.raises(ValueError, match=error):
        simulate(selected)
    assert all(not item.provider.prompts for item in selected)


def test_separate_provider_instances_with_uniform_metadata_are_accepted(
    participants: list[ConversationParticipant],
) -> None:
    assert participants[0].provider is not participants[1].provider
    run = simulate(participants[:2], turn_count=2)
    assert run.provider == "recording"
    assert run.model == "fake-v1"


def test_provider_exception_is_propagated(
    participants: list[ConversationParticipant],
) -> None:
    class FailingProvider:
        def generate(self, prompt: str, *, task_name: str) -> str:
            raise RuntimeError("provider unavailable")

    selected = [
        replace(participants[0], provider=FailingProvider()),
        participants[1],
    ]
    with pytest.raises(RuntimeError, match="provider unavailable"):
        simulate(selected, turn_count=2)


def test_local_simulation_does_not_access_network(
    participants: list[ConversationParticipant],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    run = simulate(participants[:2], turn_count=2)
    assert [message.text for message in run.messages] == [
        "response-from-alpha", "response-from-beta",
    ]


def test_mock_messages_share_run_creation_timestamp(
    participants: list[ConversationParticipant],
) -> None:
    run = simulate(participants[:2], turn_count=4)
    assert {message.timestamp for message in run.messages} == {run.created_at}


@pytest.mark.parametrize(
    "run_id",
    ["run_001", "20260803T120000.000000Z", "conversation-test-1"],
)
def test_safe_run_ids_are_accepted(
    participants: list[ConversationParticipant],
    run_id: str,
) -> None:
    run = simulate(participants[:2], run_id=run_id)
    assert run.run_id == run_id


@pytest.mark.parametrize(
    "run_id",
    [
        "../outside", "folder/run", r"folder\run", ".", "..",
        "run with spaces", "_leading", "éclair", "x" * 129,
    ],
)
def test_unsafe_run_ids_fail_before_provider_call(
    participants: list[ConversationParticipant],
    run_id: str,
) -> None:
    selected = participants[:2]
    with pytest.raises(ValueError, match="run_id"):
        simulate(selected, run_id=run_id)
    assert all(not item.provider.prompts for item in selected)
