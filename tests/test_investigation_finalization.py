"""Tests for explicit atomic investigation finalization."""

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
    finalize_investigation,
    reveal_clue,
    run_group_discussion,
    run_independent_analyses,
)
from multi_agent_personalities.models import (
    GenerationMetadata,
    GenerationResult,
    InvestigationSession,
    InvestigationStatus,
    Persona,
)
from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.simulation.participant import ConversationParticipant


ROOT = Path(__file__).resolve().parents[1]
FACTORY = DeterministicInvestigationIdFactory(1)


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


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)


def completed_round_one() -> InvestigationSession:
    return create_group_decision(
        awaiting_decision(),
        decision_provider=build_investigation_mock_bindings().decision_provider,
        id_factory=FACTORY,
    ).session


def completed_round_two() -> InvestigationSession:
    session = reveal_clue(
        completed_round_one(),
        clue_text="Mud beneath the window was undisturbed.",
        id_factory=FACTORY,
    )
    session = run_independent_analyses(
        session,
        participant_bindings=participants(),
        id_factory=FACTORY,
    ).session
    session = run_group_discussion(
        session,
        participant_bindings=participants(),
        id_factory=FACTORY,
        turn_count=2,
    ).session
    return create_group_decision(
        session,
        decision_provider=build_investigation_mock_bindings().decision_provider,
        id_factory=FACTORY,
    ).session


def final_text(**overrides: object) -> str:
    payload: dict[str, object] = {
        "summary": "The open window was staged.",
        "hypothesis_ids": ["session_001_hypothesis_0001"],
        "evidence": [
            {"clue_id": "session_001_clue_0001", "relation": "supports"}
        ],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_one_round_finalization_is_explicit_atomic_and_round_trips() -> None:
    original = completed_round_one()
    before = original.model_dump_json()
    provider = StaticProvider(final_text())

    result = finalize_investigation(
        original,
        final_theory_provider=provider,
        id_factory=FACTORY,
    )

    assert result.final_theory.final_theory_id == "session_001_final_theory"
    assert result.session.final_theory == result.final_theory
    assert result.session.status is InvestigationStatus.COMPLETED
    assert result.session.rounds == original.rounds
    assert result.session.clues == original.clues
    assert result.session.analyses == original.analyses
    assert result.session.hypotheses == original.hypotheses
    assert result.session.decisions == original.decisions
    assert original.model_dump_json() == before
    assert provider.calls == 1
    assert result.generation.generation.metadata.request_id == "request-1"
    restored = InvestigationSession.model_validate_json(
        result.session.model_dump_json()
    )
    assert restored == result.session


def test_two_round_mock_finalization_uses_fixture_and_complete_context() -> None:
    original = completed_round_two()
    provider = RecordingProvider(
        build_investigation_mock_bindings().final_theory_provider
    )
    result = finalize_investigation(
        original,
        final_theory_provider=provider,
        id_factory=FACTORY,
    )

    assert result.session.status is InvestigationStatus.COMPLETED
    assert len(result.session.rounds) == 2
    assert result.session.rounds == original.rounds
    assert provider.calls[0][1] == "investigation.final_theory"
    prompt = provider.calls[0][0]
    assert prompt.index("The study window was open.") < prompt.index(
        "Mud beneath the window was undisturbed."
    )
    assert prompt.index("session_001_hypothesis_0001") < prompt.index(
        "session_001_hypothesis_0002"
    )
    assert prompt.index("session_001_decision_0001") < prompt.index(
        "session_001_decision_0002"
    )
    assert "official solution" not in prompt.lower()


def test_final_prompt_excludes_clues_outside_final_round_visibility() -> None:
    original = completed_round_one()
    payload = original.model_dump(mode="python")
    payload["clues"] = (*payload["clues"], {
        "clue_id": "session_001_clue_0002",
        "text": "UNREVEALED FUTURE CLUE",
        "reveal_order": 1,
    })
    legacy_future = InvestigationSession.model_validate(payload)
    provider = StaticProvider(final_text())
    finalize_investigation(
        legacy_future,
        final_theory_provider=provider,
        id_factory=FACTORY,
    )
    # StaticProvider records only count; use a recorder for the prompt assertion.
    recorder = RecordingProvider(provider)
    finalize_investigation(
        legacy_future,
        final_theory_provider=recorder,
        id_factory=FACTORY,
    )
    assert "UNREVEALED FUTURE CLUE" not in recorder.calls[0][0]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "{",
        json.dumps({"summary": "missing references"}),
        final_text(summary=" "),
        final_text(hypothesis_ids=[]),
        final_text(evidence=[]),
        final_text(summary=3),
        final_text(extra="forbidden"),
    ],
)
def test_structured_and_required_reference_failures_are_atomic(text: str) -> None:
    original = completed_round_one()
    before = original.model_dump_json()
    with pytest.raises((ValueError, ValidationError)):
        finalize_investigation(
            original,
            final_theory_provider=StaticProvider(text),
            id_factory=FACTORY,
        )
    assert original.model_dump_json() == before
    assert original.status is InvestigationStatus.ACTIVE
    assert original.final_theory is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"hypothesis_ids": ["unknown"]}, "unknown hypothesis"),
        (
            {"hypothesis_ids": ["session_001_hypothesis_0001"] * 2},
            "invalid schema",
        ),
        (
            {"evidence": [{"clue_id": "unknown", "relation": "supports"}]},
            "final visible clues",
        ),
        (
            {"evidence": [
                {"clue_id": "session_001_clue_0001", "relation": "supports"},
                {"clue_id": "session_001_clue_0001", "relation": "supports"},
            ]},
            "duplicate references",
        ),
    ],
)
def test_invalid_final_references_are_atomic(
    overrides: dict[str, object], message: str
) -> None:
    original = completed_round_one()
    with pytest.raises((ValueError, ValidationError), match=message):
        finalize_investigation(
            original,
            final_theory_provider=StaticProvider(final_text(**overrides)),
            id_factory=FACTORY,
        )
    assert original.status is InvestigationStatus.ACTIVE
    assert original.final_theory is None


def test_provider_failure_and_double_finalization_call_provider_once() -> None:
    original = completed_round_one()
    failing = StaticProvider(error=RuntimeError("unavailable"))
    with pytest.raises(RuntimeError, match="unavailable"):
        finalize_investigation(
            original,
            final_theory_provider=failing,
            id_factory=FACTORY,
        )
    completed = finalize_investigation(
        original,
        final_theory_provider=StaticProvider(final_text()),
        id_factory=FACTORY,
    ).session
    unused = StaticProvider(final_text())
    before = completed.model_dump_json()
    with pytest.raises(ValueError, match="active session"):
        finalize_investigation(
            completed,
            final_theory_provider=unused,
            id_factory=FACTORY,
        )
    assert unused.calls == 0
    assert completed.model_dump_json() == before


@pytest.mark.parametrize(
    "status",
    [
        InvestigationStatus.SETUP,
        InvestigationStatus.READY_FOR_FINAL,
        InvestigationStatus.ABANDONED,
    ],
)
def test_non_operational_session_statuses_never_call_provider(
    status: InvestigationStatus,
) -> None:
    payload = completed_round_one().model_dump(mode="python")
    payload["status"] = status
    session = InvestigationSession.model_validate(payload)
    provider = StaticProvider(final_text())
    with pytest.raises(ValueError, match="active session"):
        finalize_investigation(
            session,
            final_theory_provider=provider,
            id_factory=FACTORY,
        )
    assert provider.calls == 0


def test_incomplete_or_invalid_dependencies_never_call_provider() -> None:
    provider = StaticProvider(final_text())
    with pytest.raises(ValueError, match="completed"):
        finalize_investigation(
            awaiting_decision(),
            final_theory_provider=provider,
            id_factory=FACTORY,
        )
    with pytest.raises(ValueError, match="session_id must match"):
        finalize_investigation(
            completed_round_one(),
            final_theory_provider=provider,
            id_factory=DeterministicInvestigationIdFactory(2),
        )
    with pytest.raises(ValueError, match="LLMProvider"):
        finalize_investigation(
            completed_round_one(),
            final_theory_provider=object(),  # type: ignore[arg-type]
            id_factory=FACTORY,
        )
    assert provider.calls == 0


def test_group_decisions_never_finalize_implicitly() -> None:
    one_round = completed_round_one()
    two_rounds = completed_round_two()
    assert one_round.status is InvestigationStatus.ACTIVE
    assert two_rounds.status is InvestigationStatus.ACTIVE
    assert one_round.final_theory is None
    assert two_rounds.final_theory is None
