"""Tests for conversation simulation with participant-owned providers."""

import socket
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

import multi_agent_personalities.simulation.engine as engine_module
from multi_agent_personalities.models import (
    GenerationMetadata,
    GenerationResult,
    Message,
    Persona,
)
from multi_agent_personalities.simulation import (
    ConversationParticipant,
    RoundRobinSelector,
    TurnReplyGenerator,
    simulate_chat,
)


FIXED_TIME = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)


class RecordingProvider:
    def __init__(
        self,
        response: str,
        *,
        provider_name: str = "recording",
        model_name: str | None = None,
    ) -> None:
        self.response = response
        self.provider_name = provider_name
        self.model_name = model_name
        self.prompts: list[str] = []
        self.tasks: list[str] = []

    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        self.prompts.append(prompt)
        self.tasks.append(task_name)
        return GenerationResult(
            text=self.response,
            metadata=GenerationMetadata(
                provider=self.provider_name,
                model=self.model_name,
            ),
        )


class SequenceSelector:
    def __init__(self, selections: Sequence[str]) -> None:
        self.selections = tuple(selections)

    def select_next(
        self,
        *,
        participant_ids: Sequence[str],
        history: Sequence[Message],
        turn_index: int,
    ) -> str:
        return self.selections[turn_index]


class RecordingSelector:
    def __init__(self) -> None:
        self.calls: list[tuple[Sequence[str], Sequence[Message], int]] = []

    def select_next(
        self,
        *,
        participant_ids: Sequence[str],
        history: Sequence[Message],
        turn_index: int,
    ) -> str:
        self.calls.append((participant_ids, history, turn_index))
        return participant_ids[turn_index % len(participant_ids)]


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
        speaker_selector=RoundRobinSelector(),
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
    call_counts = [
        len(item.provider.prompts)  # type: ignore[attr-defined]
        for item in participants
    ]
    assert call_counts == [2, 2, 1]
    assert sum(call_counts) == run.turn_count == len(run.messages)


def test_non_alternating_selector_controls_speakers_and_bound_providers(
    participants: list[ConversationParticipant],
) -> None:
    selections = ["alpha", "alpha", "gamma", "beta", "gamma"]

    run = simulate(
        participants,
        turn_count=5,
        speaker_selector=SequenceSelector(selections),
    )

    assert run.character_ids == ("alpha", "beta", "gamma")
    assert [message.speaker_character_id for message in run.messages] == selections
    assert [message.text for message in run.messages] == [
        f"response-from-{character_id}" for character_id in selections
    ]
    assert [message.turn_index for message in run.messages] == list(range(5))
    call_counts = [len(item.provider.prompts) for item in participants]  # type: ignore[attr-defined]
    assert call_counts == [2, 1, 2]
    assert sum(call_counts) == len(run.messages)


def test_selector_is_called_once_per_turn_with_read_only_complete_history(
    participants: list[ConversationParticipant],
) -> None:
    selector = RecordingSelector()

    run = simulate(
        participants,
        turn_count=5,
        speaker_selector=selector,
    )

    assert len(selector.calls) == 5
    assert [call[2] for call in selector.calls] == list(range(5))
    assert all(
        call[0] == ("alpha", "beta", "gamma")
        for call in selector.calls
    )
    assert [len(call[1]) for call in selector.calls] == list(range(5))
    assert all(isinstance(call[1], tuple) for call in selector.calls)
    for turn_index, (_, history, _) in enumerate(selector.calls):
        assert history == run.messages[:turn_index]


def test_invalid_selector_result_fails_before_provider_call(
    participants: list[ConversationParticipant],
) -> None:
    with pytest.raises(ValueError, match="unsupported participant identifier"):
        simulate(
            participants,
            turn_count=1,
            speaker_selector=SequenceSelector(["unknown-participant"]),
        )

    assert all(
        not item.provider.prompts  # type: ignore[attr-defined]
        for item in participants
    )


def test_selector_exception_propagates_before_provider_call(
    participants: list[ConversationParticipant],
) -> None:
    class SelectorFailure(RuntimeError):
        pass

    class FailingSelector:
        def select_next(
            self,
            *,
            participant_ids: Sequence[str],
            history: Sequence[Message],
            turn_index: int,
        ) -> str:
            raise SelectorFailure("selection unavailable")

    with pytest.raises(SelectorFailure, match="selection unavailable"):
        simulate(
            participants,
            turn_count=1,
            speaker_selector=FailingSelector(),
        )

    assert all(
        not item.provider.prompts  # type: ignore[attr-defined]
        for item in participants
    )


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
    assert all(message.provider == run.provider for message in run.messages)
    assert all(message.model == run.model for message in run.messages)
    assert all(
        message.generation_metadata is not None
        and message.generation_metadata.model is None
        for message in run.messages
    )


def test_uniform_reported_model_becomes_effective_run_model(
    participants: list[ConversationParticipant],
) -> None:
    selected = [
        replace(
            item,
            provider=RecordingProvider(
                f"response-from-{item.character_id}",
                model_name="reported-model",
            ),
            model_name=None,
        )
        for item in participants[:2]
    ]

    run = simulate(selected, turn_count=4)

    assert run.model == "reported-model"
    assert all(message.model == "reported-model" for message in run.messages)
    assert all(
        message.generation_metadata is not None
        and message.generation_metadata.model == "reported-model"
        for message in run.messages
    )


def test_no_reported_or_configured_model_keeps_run_model_absent(
    participants: list[ConversationParticipant],
) -> None:
    selected = [replace(item, model_name=None) for item in participants[:2]]
    run = simulate(selected, turn_count=2)
    assert run.model is None
    assert all(message.model is None for message in run.messages)


def test_differing_reported_models_fail_after_selected_provider_calls(
    participants: list[ConversationParticipant],
) -> None:
    selected = [
        replace(
            participants[0],
            provider=RecordingProvider("alpha", model_name="model-a"),
            model_name=None,
        ),
        replace(
            participants[1],
            provider=RecordingProvider("beta", model_name="model-b"),
            model_name=None,
        ),
    ]

    with pytest.raises(ValueError, match="one uniform model"):
        simulate(selected, turn_count=2)

    assert [len(item.provider.prompts) for item in selected] == [1, 1]  # type: ignore[attr-defined]


def test_reported_provider_mismatch_prevents_completed_run(
    participants: list[ConversationParticipant],
) -> None:
    selected = [
        replace(
            participants[0],
            provider=RecordingProvider(
                "alpha",
                provider_name="unexpected-provider",
            ),
        ),
        participants[1],
    ]
    with pytest.raises(ValueError, match="declared provider does not match"):
        simulate(selected, turn_count=2)
    assert len(selected[0].provider.prompts) == 1  # type: ignore[attr-defined]
    assert len(selected[1].provider.prompts) == 0  # type: ignore[attr-defined]


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
        def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
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


def test_default_path_still_delegates_to_standard_reply_generator(
    participants: list[ConversationParticipant],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []
    original = engine_module.generate_participant_reply

    def recording_default(**kwargs: object) -> Message:
        participant = kwargs["participant"]
        calls.append((participant.character_id, kwargs["turn_index"]))  # type: ignore[attr-defined]
        return original(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        engine_module,
        "generate_participant_reply",
        recording_default,
    )
    run = simulate(participants[:2], turn_count=3)

    assert calls == [("alpha", 0), ("beta", 1), ("alpha", 2)]
    assert [item.text for item in run.messages] == [
        "response-from-alpha", "response-from-beta", "response-from-alpha",
    ]
    assert run.provider == "recording"
    assert run.model == "fake-v1"


def test_implicit_default_equals_explicit_standard_generator(
    participants: list[ConversationParticipant],
) -> None:
    implicit = simulate(participants[:2], turn_count=3)
    explicit = simulate(
        participants[:2],
        turn_count=3,
        turn_reply_generator=engine_module.generate_participant_reply,
    )
    assert implicit == explicit


class RecordingTurnReplyGenerator:
    def __init__(self) -> None:
        self.calls: list[
            tuple[ConversationParticipant, tuple[Message, ...], str, str, int]
        ] = []

    def __call__(
        self,
        *,
        participant: ConversationParticipant,
        history: tuple[Message, ...],
        topic: str,
        run_id: str,
        turn_index: int,
        timestamp: datetime,
    ) -> Message:
        self.calls.append(
            (participant, history, topic, run_id, turn_index)
        )
        generation = participant.provider.generate(
            f"custom prompt for {participant.character_id} at {turn_index}",
            task_name=f"custom.turn.{turn_index}",
        )
        return Message(
            message_id=f"{run_id}_custom_{turn_index}",
            run_id=run_id,
            turn_index=turn_index,
            speaker_character_id=participant.character_id,
            speaker_name=participant.display_name,
            text=f"custom-{participant.character_id}-{turn_index}",
            provider=participant.provider_name,
            model=participant.model_name,
            generation_metadata=generation.metadata,
            timestamp=timestamp,
        )


def test_custom_generator_controls_generation_but_not_loop_or_speakers(
    participants: list[ConversationParticipant],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = RecordingTurnReplyGenerator()

    def forbidden_default(**kwargs: object) -> Message:
        raise AssertionError("standard generator called")

    monkeypatch.setattr(
        engine_module,
        "generate_participant_reply",
        forbidden_default,
    )
    run = simulate(
        participants[:2],
        turn_count=4,
        turn_reply_generator=generator,
    )

    assert len(generator.calls) == 4
    assert [item[0].character_id for item in generator.calls] == [
        "alpha", "beta", "alpha", "beta",
    ]
    assert [item[3] for item in generator.calls] == ["run_fixed"] * 4
    assert [item[4] for item in generator.calls] == list(range(4))
    assert [len(item[1]) for item in generator.calls] == list(range(4))
    assert all(isinstance(item[1], tuple) for item in generator.calls)
    assert [item.text for item in run.messages] == [
        "custom-alpha-0", "custom-beta-1", "custom-alpha-2", "custom-beta-3",
    ]
    assert participants[0].provider.tasks == ["custom.turn.0", "custom.turn.2"]  # type: ignore[attr-defined]
    assert participants[1].provider.tasks == ["custom.turn.1", "custom.turn.3"]  # type: ignore[attr-defined]


def test_custom_generator_receives_complete_immutable_chronological_history(
    participants: list[ConversationParticipant],
) -> None:
    class MutationCheckingGenerator(RecordingTurnReplyGenerator):
        def __call__(self, **kwargs: object) -> Message:
            history = kwargs["history"]
            with pytest.raises(AttributeError):
                history.append("bad")  # type: ignore[attr-defined]
            if history:
                with pytest.raises(ValidationError):
                    history[0].text = "changed"  # type: ignore[index,union-attr]
            return super().__call__(**kwargs)  # type: ignore[arg-type]

    generator = MutationCheckingGenerator()
    run = simulate(
        participants[:2],
        turn_count=3,
        turn_reply_generator=generator,
    )
    assert generator.calls[0][1] == ()
    assert generator.calls[1][1] == run.messages[:1]
    assert generator.calls[2][1] == run.messages[:2]
    assert run.messages == tuple(item for item in run.messages)


def test_selector_runs_before_custom_generator_and_alone_controls_speaker(
    participants: list[ConversationParticipant],
) -> None:
    events: list[tuple[str, int, str | None]] = []

    class OrderedSelector:
        def select_next(
            self,
            *,
            participant_ids: Sequence[str],
            history: Sequence[Message],
            turn_index: int,
        ) -> str:
            selected = ("gamma", "alpha", "beta")[turn_index]
            events.append(("select", turn_index, selected))
            return selected

    class OrderedGenerator(RecordingTurnReplyGenerator):
        def __call__(self, **kwargs: object) -> Message:
            selected = kwargs["participant"].character_id  # type: ignore[union-attr]
            events.append(("generate", kwargs["turn_index"], selected))  # type: ignore[arg-type]
            return super().__call__(**kwargs)  # type: ignore[arg-type]

    generator = OrderedGenerator()
    run = simulate(
        participants,
        turn_count=3,
        speaker_selector=OrderedSelector(),
        turn_reply_generator=generator,
    )
    assert events == [
        ("select", 0, "gamma"), ("generate", 0, "gamma"),
        ("select", 1, "alpha"), ("generate", 1, "alpha"),
        ("select", 2, "beta"), ("generate", 2, "beta"),
    ]
    assert [item.speaker_character_id for item in run.messages] == [
        "gamma", "alpha", "beta",
    ]


def test_custom_generator_exception_has_no_default_fallback(
    participants: list[ConversationParticipant],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_calls = 0

    def default(**kwargs: object) -> Message:
        nonlocal default_calls
        default_calls += 1
        return engine_module.generate_participant_reply(**kwargs)  # pragma: no cover

    def fail(**kwargs: object) -> Message:
        raise RuntimeError("custom failure")

    monkeypatch.setattr(engine_module, "generate_participant_reply", default)
    with pytest.raises(RuntimeError, match="custom failure"):
        simulate(
            participants[:2],
            turn_count=2,
            turn_reply_generator=fail,
        )
    assert default_calls == 0


def test_provider_error_inside_custom_generator_propagates(
    participants: list[ConversationParticipant],
) -> None:
    class FailingProvider:
        def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
            raise RuntimeError("custom provider unavailable")

    selected = [replace(participants[0], provider=FailingProvider()), participants[1]]
    with pytest.raises(RuntimeError, match="custom provider unavailable"):
        simulate(
            selected,
            turn_count=1,
            turn_reply_generator=RecordingTurnReplyGenerator(),
        )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("run_id", "wrong_run", "run_id"),
        ("turn_index", 9, "turn_index"),
        ("speaker_character_id", "beta", "speaker"),
        ("provider", "wrong-provider", "provider"),
        ("model", "wrong-model", "model"),
    ],
)
def test_engine_rejects_invalid_custom_message_ownership(
    participants: list[ConversationParticipant],
    field: str,
    value: object,
    error: str,
) -> None:
    def invalid_generator(
        *,
        participant: ConversationParticipant,
        history: tuple[Message, ...],
        topic: str,
        run_id: str,
        turn_index: int,
        timestamp: datetime,
    ) -> Message:
        del history, topic
        data: dict[str, object] = {
            "message_id": "invalid",
            "run_id": run_id,
            "turn_index": turn_index,
            "speaker_character_id": participant.character_id,
            "speaker_name": participant.display_name,
            "text": "invalid custom result",
            "provider": participant.provider_name,
            "model": participant.model_name,
            "timestamp": timestamp,
        }
        data[field] = value
        return Message.model_validate(data)

    with pytest.raises(ValueError, match=error):
        simulate(
            participants[:2],
            turn_count=1,
            turn_reply_generator=invalid_generator,
        )


def test_turn_reply_generator_protocol_accepts_callable() -> None:
    generator: TurnReplyGenerator = RecordingTurnReplyGenerator()
    assert callable(generator)


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
