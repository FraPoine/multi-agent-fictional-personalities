"""Tests for atomic independent participant analysis generation."""

import json
import socket
from pathlib import Path

import pytest
from pydantic import ValidationError

import multi_agent_personalities.application.investigation_service as service
from multi_agent_personalities.application import (
    DeterministicInvestigationIdFactory,
    GeneratedAnalysisPayload,
    StructuredOutputError,
    build_investigation_mock_bindings,
    create_session,
    reveal_clue,
    run_independent_analyses,
)
from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.models import (
    AgentAnalysis,
    GenerationMetadata,
    GenerationResult,
    GroupDecision,
    GroupDecisionType,
    InvestigationRoundStatus,
    InvestigationSession,
    InvestigationStatus,
    Persona,
    ConversationRun,
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


def personas() -> tuple[Persona, Persona]:
    return tuple(
        Persona.model_validate_json(
            (ROOT / "tests" / "fixtures" / filename).read_text(encoding="utf-8")
        )
        for filename in (
            "sherlock_persona_response.json",
            "poirot_persona_response.json",
        )
    )  # type: ignore[return-value]


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
            text=self.text or "{}",
            metadata=GenerationMetadata(provider="mock", finish_reason="completed"),
        )


def participant_bindings(
    providers: tuple[LLMProvider, LLMProvider] | None = None,
) -> tuple[ConversationParticipant, ConversationParticipant]:
    mock = build_investigation_mock_bindings()
    sherlock, poirot = personas()
    resolved = providers or (
        mock.participant_providers[sherlock.character_id],
        mock.participant_providers[poirot.character_id],
    )
    return (
        ConversationParticipant(sherlock, resolved[0], "mock"),
        ConversationParticipant(poirot, resolved[1], "mock"),
    )


def awaiting_round() -> InvestigationSession:
    session = create_session(
        id_factory=FACTORY,
        introduction="A visitor vanished from a locked study.",
        participant_ids=("sherlock_holmes", "hercule_poirot"),
    )
    return reveal_clue(
        session,
        clue_text="The study window was open.",
        id_factory=FACTORY,
    )


def complete_round_one(session: InvestigationSession) -> InvestigationSession:
    decision = GroupDecision(
        decision_id="session_001_decision_0001",
        session_id=session.session_id,
        round_id=session.rounds[0].round_id,
        decision_type=GroupDecisionType.PURSUE_LEAD,
        summary="Inspect below the window.",
        analysis_ids=session.rounds[0].analysis_ids,
        hypothesis_ids=("session_001_hypothesis_0001",),
        evidence=(),
    )
    payload = session.model_dump(mode="python")
    payload["rounds"][0]["status"] = InvestigationRoundStatus.COMPLETED
    payload["rounds"][0]["decision_id"] = decision.decision_id
    payload["decisions"] = [decision]
    return InvestigationSession.model_validate(payload)


def test_success_produces_ordered_authoritative_analyses_and_metadata() -> None:
    original = awaiting_round()
    original_json = original.model_dump_json()
    recordings = tuple(
        RecordingProvider(item.provider) for item in participant_bindings()
    )
    bindings = participant_bindings(recordings)  # type: ignore[arg-type]

    result = run_independent_analyses(
        original,
        participant_bindings=bindings,
        id_factory=FACTORY,
    )

    assert tuple(item.agent_id for item in result.session.analyses) == (
        "sherlock_holmes", "hercule_poirot",
    )
    assert result.session.rounds[-1].analysis_ids == tuple(
        item.analysis_id for item in result.session.analyses
    )
    assert result.session.rounds[-1].status is InvestigationRoundStatus.AWAITING_DISCUSSION
    assert {item.session_id for item in result.session.analyses} == {original.session_id}
    assert {item.round_id for item in result.session.analyses} == {original.rounds[-1].round_id}
    assert {item.visible_clue_ids for item in result.session.analyses} == {
        original.rounds[-1].visible_clue_ids
    }
    assert result.session.rounds[-1].discussion_run is None
    assert result.session.rounds[-1].decision_id is None
    assert len(result.generations) == 2
    assert all(item.generation.metadata.provider == "mock" for item in result.generations)
    assert all(provider.calls and len(provider.calls) == 1 for provider in recordings)
    assert original.model_dump_json() == original_json


def test_prompts_use_own_personas_same_snapshot_and_hide_peer_outputs() -> None:
    recordings = tuple(
        RecordingProvider(item.provider) for item in participant_bindings()
    )
    run_independent_analyses(
        awaiting_round(),
        participant_bindings=participant_bindings(recordings),  # type: ignore[arg-type]
        id_factory=FACTORY,
    )
    sherlock_prompt, poirot_prompt = (item.calls[0][0] for item in recordings)

    assert "Sherlock Holmes" in sherlock_prompt
    assert "Hercule Poirot" not in sherlock_prompt
    assert "Hercule Poirot" in poirot_prompt
    assert "Sherlock Holmes" not in poirot_prompt
    expected_clue = "[session_001_clue_0001] The study window was open."
    assert expected_clue in sherlock_prompt and expected_clue in poirot_prompt
    assert "SHERLOCK_R1" not in poirot_prompt
    assert "POIROT_R1" not in sherlock_prompt
    assert "discussion" not in sherlock_prompt.lower().split("completed investigation history:")[0]
    assert "decision" not in poirot_prompt.lower().split("completed investigation history:")[0]


def test_all_prompts_are_built_before_any_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rendered_personas = 0
    original_renderer = service.render_persona_context

    def track(persona: Persona) -> str:
        nonlocal rendered_personas
        rendered_personas += 1
        return original_renderer(persona)

    class AssertProvider(RecordingProvider):
        def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
            assert rendered_personas == 2
            return super().generate(prompt, task_name=task_name)

    monkeypatch.setattr(service, "render_persona_context", track)
    base = participant_bindings()
    providers = (AssertProvider(base[0].provider), AssertProvider(base[1].provider))
    run_independent_analyses(
        awaiting_round(),
        participant_bindings=participant_bindings(providers),
        id_factory=FACTORY,
    )


def analysis_text(**overrides: object) -> str:
    payload: dict[str, object] = {
        "facts": ["A fact."],
        "deductions": [],
        "evidence": [],
        "proposed_leads": [],
        "hypotheses": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


@pytest.mark.parametrize(
    ("bad_text", "error"),
    [
        ("{", StructuredOutputError),
        (json.dumps({"facts": []}), StructuredOutputError),
        (analysis_text(extra="bad"), StructuredOutputError),
        (analysis_text(facts=[], deductions=[], proposed_leads=[]), ValidationError),
        (
            analysis_text(
                evidence=[{"clue_id": "unknown", "relation": "supports"}]
            ),
            ValidationError,
        ),
    ],
)
def test_invalid_participant_output_fails_atomically(
    bad_text: str,
    error: type[Exception],
) -> None:
    original = awaiting_round()
    before = original.model_dump_json()
    good = StaticProvider(analysis_text())
    bad = StaticProvider(bad_text)
    with pytest.raises(error):
        run_independent_analyses(
            original,
            participant_bindings=participant_bindings((good, bad)),
            id_factory=FACTORY,
        )
    assert original.model_dump_json() == before
    assert original.analyses == ()
    assert original.rounds[-1].analysis_ids == ()
    assert original.rounds[-1].status is InvestigationRoundStatus.AWAITING_ANALYSES


def test_future_clue_reference_fails_even_when_clue_exists_in_session() -> None:
    original = awaiting_round()
    payload = original.model_dump(mode="python")
    payload["clues"] = (*payload["clues"],
        {"clue_id": FACTORY.clue_id(1), "text": "Hidden mud.", "reveal_order": 1},
    )
    hidden_future = InvestigationSession.model_validate(payload)
    future = StaticProvider(
        analysis_text(
            evidence=[{"clue_id": FACTORY.clue_id(1), "relation": "supports"}]
        )
    )
    with pytest.raises(ValidationError, match="outside its visibility"):
        run_independent_analyses(
            hidden_future,
            participant_bindings=participant_bindings((future, StaticProvider(analysis_text()))),
            id_factory=FACTORY,
        )


def test_second_provider_failure_is_atomic() -> None:
    original = awaiting_round()
    first = StaticProvider(analysis_text())
    second = StaticProvider(error=RuntimeError("provider failed"))
    with pytest.raises(RuntimeError, match="provider failed"):
        run_independent_analyses(
            original,
            participant_bindings=participant_bindings((first, second)),
            id_factory=FACTORY,
        )
    assert first.calls == second.calls == 1
    assert original.analyses == ()


def test_missing_extra_duplicate_and_misbound_participants_are_rejected() -> None:
    original = awaiting_round()
    valid = participant_bindings()
    extra_persona = valid[0].persona.model_copy(update={"character_id": "extra"})
    extra = ConversationParticipant(extra_persona, valid[0].provider, "mock")
    for invalid in ((valid[0],), (*valid, extra), (valid[0], valid[0])):
        with pytest.raises(ValueError, match="participant binding"):
            run_independent_analyses(
                original,
                participant_bindings=invalid,
                id_factory=FACTORY,
            )


def test_factory_session_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="session_id must match"):
        run_independent_analyses(
            awaiting_round(),
            participant_bindings=participant_bindings(),
            id_factory=DeterministicInvestigationIdFactory(2),
        )


def test_duplicate_generated_analysis_id_is_rejected_before_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        DeterministicInvestigationIdFactory,
        "analysis_id",
        lambda self, participant_id, round_index: "duplicate_analysis",
    )
    bindings = participant_bindings()
    with pytest.raises(ValueError, match="duplicate analysis_id"):
        run_independent_analyses(
            awaiting_round(), participant_bindings=bindings, id_factory=FACTORY
        )


def test_no_round_nonactive_wrong_status_and_rerun_are_rejected() -> None:
    no_round = create_session(
        id_factory=FACTORY,
        introduction="A case.",
        participant_ids=("sherlock_holmes", "hercule_poirot"),
    )
    with pytest.raises(ValueError, match="current investigation round"):
        run_independent_analyses(no_round, participant_bindings=participant_bindings(), id_factory=FACTORY)

    payload = awaiting_round().model_dump(mode="python")
    payload["status"] = InvestigationStatus.ABANDONED
    with pytest.raises(ValueError, match="active session"):
        run_independent_analyses(InvestigationSession.model_validate(payload), participant_bindings=participant_bindings(), id_factory=FACTORY)

    payload = awaiting_round().model_dump(mode="python")
    payload["rounds"][0]["status"] = InvestigationRoundStatus.AWAITING_DISCUSSION
    wrong_status = InvestigationSession.model_validate(payload)
    with pytest.raises(ValueError, match="awaiting analyses"):
        run_independent_analyses(wrong_status, participant_bindings=participant_bindings(), id_factory=FACTORY)

    completed_phase = run_independent_analyses(awaiting_round(), participant_bindings=participant_bindings(), id_factory=FACTORY).session
    with pytest.raises(ValueError, match="awaiting analyses"):
        run_independent_analyses(completed_phase, participant_bindings=participant_bindings(), id_factory=FACTORY)


def test_existing_current_analysis_is_rejected() -> None:
    original = awaiting_round()
    analysis = AgentAnalysis(
        analysis_id=FACTORY.analysis_id("sherlock_holmes", 1),
        session_id=original.session_id,
        round_id=original.rounds[0].round_id,
        agent_id="sherlock_holmes",
        visible_clue_ids=original.rounds[0].visible_clue_ids,
        facts=("Already present.",),
    )
    payload = original.model_dump(mode="python")
    payload["analyses"] = [analysis]
    payload["rounds"][0]["analysis_ids"] = [analysis.analysis_id]
    existing = InvestigationSession.model_validate(payload)

    with pytest.raises(ValueError, match="already contains analyses"):
        run_independent_analyses(
            existing,
            participant_bindings=participant_bindings(),
            id_factory=FACTORY,
        )


def test_existing_discussion_is_rejected() -> None:
    original = awaiting_round()
    discussion = ConversationRun(
        run_id="discussion",
        topic="Case discussion.",
        character_ids=original.participant_ids,
        turn_count=1,
        seed=42,
        provider="mock",
        created_at="2026-08-06T12:00:00Z",
        status="running",
    )
    payload = original.model_dump(mode="python")
    payload["rounds"][0]["discussion_run"] = discussion
    invalid_stage = InvestigationSession.model_validate(payload)

    with pytest.raises(ValueError, match="must not contain a discussion"):
        run_independent_analyses(
            invalid_stage,
            participant_bindings=participant_bindings(),
            id_factory=FACTORY,
        )


def test_incomplete_earlier_round_is_rejected() -> None:
    first = awaiting_round()
    payload = first.model_dump(mode="python")
    payload["clues"] = (*payload["clues"], {
        "clue_id": FACTORY.clue_id(1),
        "text": "A second clue.",
        "reveal_order": 1,
    })
    payload["rounds"] = (*payload["rounds"], {
        "session_id": first.session_id,
        "round_id": FACTORY.round_id(2),
        "round_index": 2,
        "revealed_clue_id": FACTORY.clue_id(1),
        "visible_clue_ids": (FACTORY.clue_id(0), FACTORY.clue_id(1)),
        "status": InvestigationRoundStatus.AWAITING_ANALYSES,
    })
    two_incomplete = InvestigationSession.model_validate(payload)

    with pytest.raises(ValueError, match="previous rounds must be completed"):
        run_independent_analyses(
            two_incomplete,
            participant_bindings=participant_bindings(),
            id_factory=FACTORY,
        )


def test_duplicate_evidence_is_rejected_by_domain_validation() -> None:
    reference = {"clue_id": FACTORY.clue_id(0), "relation": "supports"}
    duplicate = StaticProvider(analysis_text(evidence=[reference, reference]))
    with pytest.raises(ValidationError, match="duplicate references"):
        run_independent_analyses(
            awaiting_round(),
            participant_bindings=participant_bindings(
                (duplicate, StaticProvider(analysis_text()))
            ),
            id_factory=FACTORY,
        )


def test_two_round_analysis_includes_completed_history_and_preserves_round_one() -> None:
    round_one = run_independent_analyses(
        awaiting_round(), participant_bindings=participant_bindings(), id_factory=FACTORY
    ).session
    completed = complete_round_one(round_one)
    round_one_json = completed.rounds[0].model_dump_json()
    round_two = reveal_clue(completed, clue_text="Mud below the window was undisturbed.", id_factory=FACTORY)
    recordings = tuple(RecordingProvider(item.provider) for item in participant_bindings())

    result = run_independent_analyses(
        round_two,
        participant_bindings=participant_bindings(recordings),  # type: ignore[arg-type]
        id_factory=FACTORY,
    )

    assert result.session.rounds[0].model_dump_json() == round_one_json
    assert all(len(item.visible_clue_ids) == 2 for item in result.session.analyses[-2:])
    assert result.session.rounds[1].analysis_ids == (
        "session_001_analysis_sherlock_holmes_0002",
        "session_001_analysis_hercule_poirot_0002",
    )
    for provider in recordings:
        prompt = provider.calls[0][0]
        assert "SHERLOCK_R1" in prompt
        assert "POIROT_R1" in prompt
        assert "session_001_decision_0001" in prompt
        assert "session_001_clue_0001" in prompt
        assert "session_001_clue_0002" in prompt


def test_operation_is_offline_and_requires_no_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_independent_analyses(
        awaiting_round(), participant_bindings=participant_bindings(), id_factory=FACTORY
    )
    assert len(result.session.analyses) == 2
