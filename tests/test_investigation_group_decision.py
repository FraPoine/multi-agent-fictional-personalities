"""Tests for atomic structured group-decision generation."""

import json
import socket
from pathlib import Path

import pytest
from pydantic import ValidationError

from multi_agent_personalities.application import (
    DeterministicInvestigationIdFactory,
    build_investigation_mock_bindings,
    create_group_decision,
    create_session,
    reveal_clue,
    run_group_discussion,
    run_independent_analyses,
)
from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.models import (
    GenerationMetadata,
    GenerationResult,
    GroupDecisionType,
    InvestigationRoundStatus,
    InvestigationSession,
    InvestigationStatus,
    Persona,
)
from multi_agent_personalities.simulation.participant import ConversationParticipant


ROOT = Path(__file__).resolve().parents[1]
FACTORY = DeterministicInvestigationIdFactory(1)


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)


def participants() -> tuple[ConversationParticipant, ConversationParticipant]:
    bindings = build_investigation_mock_bindings()
    personas = tuple(
        Persona.model_validate_json(
            (ROOT / "tests" / "fixtures" / filename).read_text(encoding="utf-8")
        )
        for filename in (
            "sherlock_persona_response.json",
            "poirot_persona_response.json",
        )
    )
    return tuple(
        ConversationParticipant(
            persona,
            bindings.participant_providers[persona.character_id],
            "mock",
        )
        for persona in personas
    )  # type: ignore[return-value]


def awaiting_decision() -> InvestigationSession:
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
        participant_bindings=participants(),
        id_factory=FACTORY,
    ).session
    return run_group_discussion(
        session,
        participant_bindings=participants(),
        id_factory=FACTORY,
        turn_count=2,
    ).session


class RecordingProvider:
    def __init__(self, delegate: LLMProvider) -> None:
        self.delegate = delegate
        self.calls: list[tuple[str, str]] = []

    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        self.calls.append((prompt, task_name))
        return self.delegate.generate(prompt, task_name=task_name)


class StaticProvider:
    def __init__(self, text: str | None = None, error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls = 0

    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return GenerationResult(
            text=self.text or "",
            metadata=GenerationMetadata(
                provider="mock",
                model="fixture-model",
                latency_ms=12.5,
                request_id="request-1",
                finish_reason="completed",
                retry_count=2,
            ),
        )


def decision_text(**overrides: object) -> str:
    payload: dict[str, object] = {
        "decision_type": "pursue_lead",
        "summary": "Inspect below the window.",
        "analysis_ids": [
            "session_001_analysis_sherlock_holmes_0001",
            "session_001_analysis_hercule_poirot_0001",
        ],
        "hypothesis_ids": ["session_001_hypothesis_0001"],
        "evidence": [
            {"clue_id": "session_001_clue_0001", "relation": "context"}
        ],
        "hypotheses": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_success_records_one_decision_and_preserves_generation() -> None:
    original = awaiting_decision()
    before = original.model_dump_json()
    discussion = original.rounds[-1].discussion_run
    analyses = original.analyses
    provider = RecordingProvider(build_investigation_mock_bindings().decision_provider)

    result = create_group_decision(
        original,
        decision_provider=provider,
        id_factory=FACTORY,
    )

    assert result.decision.decision_id == "session_001_decision_0001"
    assert result.decision.session_id == original.session_id
    assert result.decision.round_id == original.rounds[-1].round_id
    assert result.session.decisions == (result.decision,)
    assert result.session.rounds[-1].decision_id == result.decision.decision_id
    assert result.session.rounds[-1].status is InvestigationRoundStatus.COMPLETED
    assert result.session.rounds[-1].discussion_run == discussion
    assert result.session.analyses == analyses
    assert result.session.clues == original.clues
    assert len(result.session.rounds) == len(original.rounds)
    assert result.session.status is InvestigationStatus.ACTIVE
    assert result.session.final_theory is None
    assert original.model_dump_json() == before
    assert result.generation.generation == provider.delegate.generate(
        "ignored", task_name="investigation.decision.round_0001"
    )
    assert provider.calls[0][1] == "investigation.decision.round_0001"
    assert len(provider.calls) == 1


@pytest.mark.parametrize("decision_type", tuple(GroupDecisionType))
def test_all_decision_types_are_recorded_without_execution(
    decision_type: GroupDecisionType,
) -> None:
    original = awaiting_decision()
    result = create_group_decision(
        original,
        decision_provider=StaticProvider(
            decision_text(decision_type=decision_type.value)
        ),
        id_factory=FACTORY,
    )
    assert result.decision.decision_type is decision_type
    assert result.session.clues == original.clues
    assert len(result.session.rounds) == 1
    assert result.session.status is InvestigationStatus.ACTIVE


def test_prompt_contains_only_valid_ordered_decision_context() -> None:
    session = awaiting_decision()
    payload = session.model_dump(mode="python")
    payload["clues"] = (*payload["clues"], {
        "clue_id": "session_001_clue_0002",
        "text": "FUTURE SECRET CLUE",
        "reveal_order": 1,
    })
    session_with_future_clue = InvestigationSession.model_validate(payload)
    provider = RecordingProvider(build_investigation_mock_bindings().decision_provider)

    create_group_decision(
        session_with_future_clue,
        decision_provider=provider,
        id_factory=FACTORY,
    )
    prompt = provider.calls[0][0]
    assert "A visitor vanished from a locked study." in prompt
    assert "The study window was open." in prompt
    assert prompt.index("SHERLOCK_R1") < prompt.index("POIROT_R1")
    assert "Sherlock Holmes:" in prompt and "Hercule Poirot:" in prompt
    assert "session_001_hypothesis_0001" in prompt
    assert "FUTURE SECRET CLUE" not in prompt
    assert "final theory" not in prompt.lower()


@pytest.mark.parametrize(
    "text",
    [
        "{",
        "",
        json.dumps({"summary": "missing fields"}),
        decision_text(extra="forbidden"),
        decision_text(decision_type="invalid"),
        decision_text(summary=3),
    ],
)
def test_structured_output_failures_are_atomic(text: str) -> None:
    original = awaiting_decision()
    before = original.model_dump_json()
    with pytest.raises((ValueError, ValidationError)):
        create_group_decision(
            original,
            decision_provider=StaticProvider(text),
            id_factory=FACTORY,
        )
    assert original.model_dump_json() == before
    assert original.rounds[-1].status is InvestigationRoundStatus.AWAITING_DECISION
    assert original.decisions == ()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"analysis_ids": ["unknown"]}, "current-round analyses"),
        ({"hypothesis_ids": ["unknown"]}, "pre-decision hypotheses"),
        ({"evidence": [{"clue_id": "unknown", "relation": "context"}]}, "visible clues"),
    ],
)
def test_invalid_references_fail_atomically(
    overrides: dict[str, object], message: str
) -> None:
    original = awaiting_decision()
    before = original.model_dump_json()
    with pytest.raises(ValueError, match=message):
        create_group_decision(
            original,
            decision_provider=StaticProvider(decision_text(**overrides)),
            id_factory=FACTORY,
        )
    assert original.model_dump_json() == before
    assert original.hypotheses == awaiting_decision().hypotheses


def test_optional_hypothesis_revision_rules() -> None:
    original = awaiting_decision()
    previous_id = original.hypotheses[0].hypothesis_id
    proposal = {
        "statement": "A refined theory.",
        "status": "active",
        "evidence": [],
        "previous_hypothesis_id": previous_id,
    }
    result = create_group_decision(
        original,
        decision_provider=StaticProvider(decision_text(hypotheses=[proposal])),
        id_factory=FACTORY,
    )
    assert result.session.hypotheses[-1].hypothesis_id == (
        "session_001_hypothesis_0002"
    )
    assert result.session.hypotheses[-1].previous_hypothesis_id == previous_id

    generated_id = "session_001_hypothesis_0002"
    invalid = [
        {**proposal, "previous_hypothesis_id": None},
        {**proposal, "previous_hypothesis_id": generated_id},
    ]
    with pytest.raises(ValueError, match="pre-decision snapshot"):
        create_group_decision(
            original,
            decision_provider=StaticProvider(decision_text(hypotheses=invalid)),
            id_factory=FACTORY,
        )


def test_provider_failure_and_duplicate_execution_are_atomic() -> None:
    original = awaiting_decision()
    with pytest.raises(RuntimeError, match="unavailable"):
        create_group_decision(
            original,
            decision_provider=StaticProvider(error=RuntimeError("unavailable")),
            id_factory=FACTORY,
        )

    provider = StaticProvider(decision_text())
    first = create_group_decision(
        original, decision_provider=provider, id_factory=FACTORY
    ).session
    first_json = first.model_dump_json()
    with pytest.raises(ValueError, match="awaiting decision"):
        create_group_decision(first, decision_provider=provider, id_factory=FACTORY)
    assert provider.calls == 1
    assert first.model_dump_json() == first_json


def test_invalid_operation_state_and_dependencies_do_not_call_provider() -> None:
    provider = StaticProvider(decision_text())
    no_round = create_session(
        id_factory=FACTORY,
        introduction="A case.",
        participant_ids=("sherlock_holmes", "hercule_poirot"),
    )
    with pytest.raises(ValueError, match="current investigation round"):
        create_group_decision(no_round, decision_provider=provider, id_factory=FACTORY)
    with pytest.raises(ValueError, match="session_id must match"):
        create_group_decision(
            awaiting_decision(),
            decision_provider=provider,
            id_factory=DeterministicInvestigationIdFactory(2),
        )
    with pytest.raises(ValueError, match="LLMProvider"):
        create_group_decision(
            awaiting_decision(), decision_provider=object(), id_factory=FACTORY  # type: ignore[arg-type]
        )
    assert provider.calls == 0


def test_round_two_decision_preserves_round_one_and_uses_round_two_ids() -> None:
    round_one = create_group_decision(
        awaiting_decision(),
        decision_provider=build_investigation_mock_bindings().decision_provider,
        id_factory=FACTORY,
    ).session
    round_one_json = round_one.rounds[0].model_dump_json()
    round_two = reveal_clue(
        round_one,
        clue_text="Mud beneath the window was undisturbed.",
        id_factory=FACTORY,
    )
    round_two = run_independent_analyses(
        round_two,
        participant_bindings=participants(),
        id_factory=FACTORY,
    ).session
    round_two = run_group_discussion(
        round_two,
        participant_bindings=participants(),
        id_factory=FACTORY,
        turn_count=2,
    ).session
    provider = RecordingProvider(build_investigation_mock_bindings().decision_provider)

    result = create_group_decision(
        round_two,
        decision_provider=provider,
        id_factory=FACTORY,
    )

    assert result.decision.decision_id == "session_001_decision_0002"
    assert result.decision.round_id == "session_001_round_0002"
    assert result.session.rounds[0].model_dump_json() == round_one_json
    assert result.session.rounds[1].decision_id == result.decision.decision_id
    assert provider.calls == [
        (provider.calls[0][0], "investigation.decision.round_0002")
    ]
    assert result.session.status is InvestigationStatus.ACTIVE
