"""Tests for atomic round-robin investigation group discussion."""

import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from multi_agent_personalities.application import (
    MAX_DISCUSSION_TURNS,
    DeterministicInvestigationIdFactory,
    build_investigation_mock_bindings,
    create_session,
    reveal_clue,
    run_group_discussion,
    run_independent_analyses,
)
from multi_agent_personalities.models import (
    GenerationMetadata,
    GenerationResult,
    GroupDecision,
    GroupDecisionType,
    InvestigationRoundStatus,
    InvestigationSession,
    InvestigationStatus,
    Persona,
    TokenUsage,
)
from multi_agent_personalities.simulation.participant import ConversationParticipant


ROOT = Path(__file__).resolve().parents[1]
FACTORY = DeterministicInvestigationIdFactory(1)
FIXED_TIME = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)


def personas() -> tuple[Persona, Persona]:
    result = tuple(
        Persona.model_validate_json(
            (ROOT / "tests" / "fixtures" / filename).read_text(encoding="utf-8")
        )
        for filename in (
            "sherlock_persona_response.json",
            "poirot_persona_response.json",
        )
    )
    return result  # type: ignore[return-value]


def mock_participants() -> tuple[ConversationParticipant, ConversationParticipant]:
    mock = build_investigation_mock_bindings()
    sherlock, poirot = personas()
    return (
        ConversationParticipant(
            sherlock, mock.participant_providers[sherlock.character_id], "mock"
        ),
        ConversationParticipant(
            poirot, mock.participant_providers[poirot.character_id], "mock"
        ),
    )


class DynamicProvider:
    def __init__(self, marker: str, fail_on_call: int | None = None) -> None:
        self.marker = marker
        self.fail_on_call = fail_on_call
        self.calls: list[tuple[str, str]] = []

    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        self.calls.append((prompt, task_name))
        if self.fail_on_call == len(self.calls):
            raise RuntimeError(f"{self.marker} provider failed")
        return GenerationResult(
            text=f"{self.marker} reply {len(self.calls)}",
            metadata=GenerationMetadata(
                provider="mock",
                model="discussion-model",
                usage=TokenUsage(input_tokens=10, output_tokens=4),
                finish_reason="completed",
                request_id=f"{self.marker}-{len(self.calls)}",
                latency_ms=1.5,
            ),
        )


def dynamic_participants(
    providers: tuple[DynamicProvider, DynamicProvider] | None = None,
) -> tuple[ConversationParticipant, ConversationParticipant]:
    sherlock, poirot = personas()
    resolved = providers or (
        DynamicProvider("sherlock"), DynamicProvider("poirot")
    )
    return (
        ConversationParticipant(
            sherlock, resolved[0], "mock", "discussion-model"
        ),
        ConversationParticipant(
            poirot, resolved[1], "mock", "discussion-model"
        ),
    )


def awaiting_discussion(round_index: int = 1) -> InvestigationSession:
    session = create_session(
        id_factory=FACTORY,
        introduction="A visitor vanished from a locked study.",
        participant_ids=("sherlock_holmes", "hercule_poirot"),
    )
    session = reveal_clue(
        session,
        clue_text="The study window was open.",
        id_factory=FACTORY,
    )
    session = run_independent_analyses(
        session,
        participant_bindings=mock_participants(),
        id_factory=FACTORY,
    ).session
    if round_index == 1:
        return session
    discussed = run_group_discussion(
        session,
        participant_bindings=mock_participants(),
        id_factory=FACTORY,
        turn_count=2,
        timestamp=FIXED_TIME,
    ).session
    decision = GroupDecision(
        decision_id="session_001_decision_0001",
        session_id=discussed.session_id,
        round_id=discussed.rounds[0].round_id,
        decision_type=GroupDecisionType.PURSUE_LEAD,
        summary="Inspect the ground below the window.",
        analysis_ids=discussed.rounds[0].analysis_ids,
        hypothesis_ids=(FACTORY.hypothesis_id(1),),
    )
    payload = discussed.model_dump(mode="python")
    payload["rounds"][0]["decision_id"] = decision.decision_id
    payload["rounds"][0]["status"] = InvestigationRoundStatus.COMPLETED
    payload["decisions"] = [decision]
    completed = InvestigationSession.model_validate(payload)
    second = reveal_clue(
        completed,
        clue_text="Mud below the window was undisturbed.",
        id_factory=FACTORY,
    )
    return run_independent_analyses(
        second,
        participant_bindings=mock_participants(),
        id_factory=FACTORY,
    ).session


def test_success_attaches_complete_run_and_only_advances_round() -> None:
    original = awaiting_discussion()
    before = original.model_dump_json()
    analyses_json = tuple(item.model_dump_json() for item in original.analyses)
    hypotheses = original.hypotheses

    result = run_group_discussion(
        original,
        participant_bindings=mock_participants(),
        id_factory=FACTORY,
        turn_count=2,
        timestamp=FIXED_TIME,
    )

    assert result.conversation_run.status == "completed"
    assert result.session.rounds[0].discussion_run == result.conversation_run
    assert result.session.rounds[0].status is InvestigationRoundStatus.AWAITING_DECISION
    assert result.conversation_run.run_id == "session_001_round_0001_discussion"
    assert result.conversation_run.topic == "Investigation discussion for round 1"
    assert result.conversation_run.character_ids == original.participant_ids
    assert [item.speaker_character_id for item in result.conversation_run.messages] == [
        "sherlock_holmes", "hercule_poirot",
    ]
    assert tuple(item.model_dump_json() for item in result.session.analyses) == analyses_json
    assert result.session.hypotheses == hypotheses
    assert result.session.decisions == ()
    assert result.session.rounds[0].decision_id is None
    assert original.model_dump_json() == before


def test_round_robin_repeats_in_session_order_deterministically() -> None:
    first_providers = (DynamicProvider("sherlock"), DynamicProvider("poirot"))
    second_providers = (DynamicProvider("sherlock"), DynamicProvider("poirot"))
    first = run_group_discussion(
        awaiting_discussion(),
        participant_bindings=dynamic_participants(first_providers),
        id_factory=FACTORY,
        turn_count=4,
        timestamp=FIXED_TIME,
    ).conversation_run
    second = run_group_discussion(
        awaiting_discussion(),
        participant_bindings=dynamic_participants(second_providers),
        id_factory=FACTORY,
        turn_count=4,
        timestamp=FIXED_TIME,
    ).conversation_run
    expected = ["sherlock_holmes", "hercule_poirot"] * 2
    assert [item.speaker_character_id for item in first.messages] == expected
    assert [item.speaker_character_id for item in second.messages] == expected


def test_prompts_include_full_history_context_and_correct_persona() -> None:
    providers = (DynamicProvider("sherlock"), DynamicProvider("poirot"))
    result = run_group_discussion(
        awaiting_discussion(),
        participant_bindings=dynamic_participants(providers),
        id_factory=FACTORY,
        turn_count=3,
        timestamp=FIXED_TIME,
    )
    prompts = [providers[0].calls[0][0], providers[1].calls[0][0], providers[0].calls[1][0]]
    assert "Discussion so far:\nNone." in prompts[0]
    assert "sherlock reply 1" in prompts[1]
    assert "sherlock reply 1" in prompts[2]
    assert "poirot reply 1" in prompts[2]
    assert prompts[2].index("sherlock reply 1") < prompts[2].index("poirot reply 1")
    sherlock_persona = prompts[0].split("Participant persona:\n", 1)[1].split(
        "\nVisible clues:", 1
    )[0]
    poirot_persona = prompts[1].split("Participant persona:\n", 1)[1].split(
        "\nVisible clues:", 1
    )[0]
    assert "Sherlock Holmes" in sherlock_persona
    assert "Hercule Poirot" not in sherlock_persona
    assert "Hercule Poirot" in poirot_persona
    assert "Sherlock Holmes" not in poirot_persona
    assert result.conversation_run.messages[0].text == "sherlock reply 1"


def test_discussion_prompt_does_not_include_future_session_clues() -> None:
    original = awaiting_discussion()
    payload = original.model_dump(mode="python")
    payload["clues"] = (*payload["clues"], {
        "clue_id": FACTORY.clue_id(1),
        "text": "FUTURE HIDDEN CLUE",
        "reveal_order": 1,
    })
    hidden = InvestigationSession.model_validate(payload)
    providers = (DynamicProvider("sherlock"), DynamicProvider("poirot"))
    run_group_discussion(
        hidden,
        participant_bindings=dynamic_participants(providers),
        id_factory=FACTORY,
        turn_count=2,
        timestamp=FIXED_TIME,
    )
    for provider in providers:
        prompt = provider.calls[0][0]
        assert "A visitor vanished" in prompt
        assert "session_001_clue_0001" in prompt
        assert "SHERLOCK_R1" in prompt and "POIROT_R1" in prompt
        assert "FUTURE HIDDEN CLUE" not in prompt
        assert "decision" not in prompt.lower().split("completed investigation history:")[0]


def test_generation_metadata_and_json_round_trip_are_preserved() -> None:
    result = run_group_discussion(
        awaiting_discussion(),
        participant_bindings=dynamic_participants(),
        id_factory=FACTORY,
        turn_count=2,
        timestamp=FIXED_TIME,
    )
    for index, message in enumerate(result.conversation_run.messages):
        assert message.run_id == result.conversation_run.run_id
        assert message.turn_index == index
        assert message.provider == "mock"
        assert message.model == "discussion-model"
        assert message.generation_metadata is not None
        assert message.generation_metadata.usage == TokenUsage(
            input_tokens=10, output_tokens=4
        )
        assert message.generation_metadata.latency_ms == 1.5
    assert InvestigationSession.model_validate_json(
        result.session.model_dump_json()
    ) == result.session


@pytest.mark.parametrize("turn_count", [0, -1, True, 1.0, "2", 101])
def test_invalid_turn_counts_are_rejected(turn_count: object) -> None:
    with pytest.raises(ValueError, match="turn_count"):
        run_group_discussion(
            awaiting_discussion(),
            participant_bindings=mock_participants(),
            id_factory=FACTORY,
            turn_count=turn_count,  # type: ignore[arg-type]
        )


def test_maximum_turn_bound_is_documented() -> None:
    assert MAX_DISCUSSION_TURNS == 100


def test_state_binding_and_factory_preconditions() -> None:
    active_no_round = create_session(
        id_factory=FACTORY,
        introduction="A case.",
        participant_ids=("sherlock_holmes", "hercule_poirot"),
    )
    with pytest.raises(ValueError, match="current investigation round"):
        run_group_discussion(active_no_round, participant_bindings=mock_participants(), id_factory=FACTORY, turn_count=2)

    payload = awaiting_discussion().model_dump(mode="python")
    payload["status"] = InvestigationStatus.ABANDONED
    with pytest.raises(ValueError, match="active session"):
        run_group_discussion(InvestigationSession.model_validate(payload), participant_bindings=mock_participants(), id_factory=FACTORY, turn_count=2)

    not_ready = reveal_clue(active_no_round, clue_text="A clue.", id_factory=FACTORY)
    with pytest.raises(ValueError, match="awaiting discussion"):
        run_group_discussion(not_ready, participant_bindings=mock_participants(), id_factory=FACTORY, turn_count=2)

    with pytest.raises(ValueError, match="participant binding"):
        run_group_discussion(awaiting_discussion(), participant_bindings=mock_participants()[:1], id_factory=FACTORY, turn_count=2)
    with pytest.raises(ValueError, match="session_id must match"):
        run_group_discussion(awaiting_discussion(), participant_bindings=mock_participants(), id_factory=DeterministicInvestigationIdFactory(2), turn_count=2)


def test_missing_or_misordered_current_analyses_are_rejected() -> None:
    original = awaiting_discussion()
    missing_payload = original.model_dump(mode="python")
    missing_payload["analyses"] = missing_payload["analyses"][:1]
    missing_payload["rounds"][0]["analysis_ids"] = missing_payload["rounds"][0]["analysis_ids"][:1]
    with pytest.raises(ValidationError, match="one ordered analysis per participant"):
        InvestigationSession.model_validate(missing_payload)

    reversed_payload = original.model_dump(mode="python")
    reversed_payload["analyses"] = tuple(reversed(reversed_payload["analyses"]))
    reversed_payload["rounds"][0]["analysis_ids"] = tuple(reversed(reversed_payload["rounds"][0]["analysis_ids"]))
    with pytest.raises(ValidationError, match="one ordered analysis per participant"):
        InvestigationSession.model_validate(reversed_payload)


def test_duplicate_execution_is_rejected_without_modification() -> None:
    first = run_group_discussion(
        awaiting_discussion(), participant_bindings=mock_participants(),
        id_factory=FACTORY, turn_count=2, timestamp=FIXED_TIME,
    ).session
    before = first.model_dump_json()
    with pytest.raises(ValueError, match="awaiting discussion"):
        run_group_discussion(first, participant_bindings=mock_participants(), id_factory=FACTORY, turn_count=2)
    assert first.model_dump_json() == before


def test_selector_is_injected_but_cannot_escape_session() -> None:
    class PoirotFirst:
        def select_next(self, *, participant_ids, history, turn_index):
            return participant_ids[(turn_index + 1) % len(participant_ids)]

    providers = (DynamicProvider("sherlock"), DynamicProvider("poirot"))
    result = run_group_discussion(
        awaiting_discussion(), participant_bindings=dynamic_participants(providers),
        id_factory=FACTORY, turn_count=2, selector=PoirotFirst(), timestamp=FIXED_TIME,
    )
    assert [item.speaker_character_id for item in result.conversation_run.messages] == [
        "hercule_poirot", "sherlock_holmes",
    ]

    class Unknown:
        def select_next(self, *, participant_ids, history, turn_index):
            return "unknown"

    with pytest.raises(ValueError, match="unsupported participant"):
        run_group_discussion(awaiting_discussion(), participant_bindings=dynamic_participants(), id_factory=FACTORY, turn_count=1, selector=Unknown())

    class Exploding:
        def select_next(self, *, participant_ids, history, turn_index):
            raise RuntimeError("selector failed")

    with pytest.raises(RuntimeError, match="selector failed"):
        run_group_discussion(awaiting_discussion(), participant_bindings=dynamic_participants(), id_factory=FACTORY, turn_count=1, selector=Exploding())
    with pytest.raises(AttributeError):
        run_group_discussion(awaiting_discussion(), participant_bindings=dynamic_participants(), id_factory=FACTORY, turn_count=1, selector=object())  # type: ignore[arg-type]


def test_later_turn_failure_is_atomic() -> None:
    original = awaiting_discussion()
    before = original.model_dump_json()
    providers = (DynamicProvider("sherlock"), DynamicProvider("poirot", fail_on_call=1))
    with pytest.raises(RuntimeError, match="poirot provider failed"):
        run_group_discussion(
            original, participant_bindings=dynamic_participants(providers),
            id_factory=FACTORY, turn_count=2, timestamp=FIXED_TIME,
        )
    assert len(providers[0].calls) == len(providers[1].calls) == 1
    assert original.model_dump_json() == before
    assert original.rounds[-1].discussion_run is None
    assert original.rounds[-1].status is InvestigationRoundStatus.AWAITING_DISCUSSION


def test_two_round_discussion_attaches_only_to_round_two() -> None:
    original = awaiting_discussion(round_index=2)
    first_round_json = original.rounds[0].model_dump_json()
    providers = (DynamicProvider("sherlock"), DynamicProvider("poirot"))
    result = run_group_discussion(
        original, participant_bindings=dynamic_participants(providers),
        id_factory=FACTORY, turn_count=2, timestamp=FIXED_TIME,
    )
    assert result.session.rounds[0].model_dump_json() == first_round_json
    assert result.session.rounds[1].discussion_run == result.conversation_run
    assert result.conversation_run.run_id == "session_001_round_0002_discussion"
    assert all("round_0002" in task for provider in providers for _, task in provider.calls)
    assert all("session_001_clue_0002" in provider.calls[0][0] for provider in providers)


def test_incomplete_previous_round_is_rejected() -> None:
    original = awaiting_discussion(round_index=2)
    payload = original.model_dump(mode="python")
    payload["rounds"][0]["status"] = InvestigationRoundStatus.AWAITING_DECISION
    payload["rounds"][0]["decision_id"] = None
    payload["decisions"] = ()
    incomplete = InvestigationSession.model_validate(payload)

    with pytest.raises(ValueError, match="previous rounds must be completed"):
        run_group_discussion(
            incomplete,
            participant_bindings=dynamic_participants(),
            id_factory=FACTORY,
            turn_count=2,
        )


def test_offline_execution_does_not_require_key_or_persist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    before = tuple(tmp_path.iterdir())
    run_group_discussion(
        awaiting_discussion(), participant_bindings=mock_participants(),
        id_factory=FACTORY, turn_count=2, timestamp=FIXED_TIME,
    )
    assert tuple(tmp_path.iterdir()) == before
