"""Optional reasoning and explicit finalization for Lead/Visit sessions."""

from datetime import datetime, timezone

import pytest

from multi_agent_personalities.application import (
    DeterministicInvestigationIdFactory,
    StructuredOutputError,
    build_investigation_mock_runtime,
    continue_lead_discussion,
    create_session,
    finalize_lead_investigation,
    record_group_decision,
    record_hypothesis,
    record_visit_analysis,
    reveal_information,
    visit_lead,
)
from multi_agent_personalities.models import (
    EvidenceReference,
    GenerationMetadata,
    GenerationResult,
    GroupDecisionType,
    HypothesisStatus,
    InvestigationStatus,
)


NOW = datetime(2026, 8, 31, 14, 0, tzinfo=timezone.utc)


class StaticProvider:
    def __init__(self, text: str, *, fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        self.calls.append((prompt, task_name))
        if self.fail:
            raise RuntimeError("provider failure")
        return GenerationResult(
            text=self.text,
            metadata=GenerationMetadata(provider="mock"),
        )


def prepared_session():
    factory = DeterministicInvestigationIdFactory(1)
    session = create_session(
        id_factory=factory,
        introduction="A visitor vanished after midnight.",
        participant_ids=("sherlock_holmes", "hercule_poirot"),
    )
    session = visit_lead(
        session, id_factory=factory, label="Lead A", kind="person"
    )
    session = reveal_information(
        session,
        visit_id=session.visits[-1].visit_id,
        information_texts=("The window was open.", "The corridor was used."),
        id_factory=factory,
    )
    return session, factory


def info_ref(index: int, relation: str = "supports") -> EvidenceReference:
    return EvidenceReference(
        information_id=f"session_001_info_{index:04d}", relation=relation
    )


def test_reasoning_artifacts_are_optional_visit_owned_and_non_gating() -> None:
    session, factory = prepared_session()
    visit_id = session.visits[-1].visit_id
    session = record_visit_analysis(
        session,
        visit_id=visit_id,
        agent_id="sherlock_holmes",
        facts=("The window is open.",),
        evidence=(info_ref(1),),
        id_factory=factory,
    )
    session = record_hypothesis(
        session,
        origin_visit_id=visit_id,
        statement="The window was staged.",
        status=HypothesisStatus.ACTIVE,
        evidence=(info_ref(1),),
        id_factory=factory,
    )
    session = record_hypothesis(
        session,
        origin_visit_id=visit_id,
        statement="The corridor was the real route.",
        status=HypothesisStatus.ACTIVE,
        evidence=(info_ref(2),),
        previous_hypothesis_id=session.hypotheses[-1].hypothesis_id,
        id_factory=factory,
    )
    session = record_group_decision(
        session,
        origin_visit_id=visit_id,
        decision_type=GroupDecisionType.PURSUE_LEAD,
        summary="Inspect another location.",
        analysis_ids=(session.analyses[-1].analysis_id,),
        hypothesis_ids=(session.hypotheses[-1].hypothesis_id,),
        evidence=(info_ref(2),),
        id_factory=factory,
    )
    session = visit_lead(
        session, id_factory=factory, label="Lead B", kind="location"
    )

    assert session.status is InvestigationStatus.ACTIVE
    assert session.analyses[0].origin_visit_id == visit_id
    assert session.hypotheses[0].round_id is None
    assert session.decisions[0].round_id is None
    assert len(session.visits) == 2


def test_hypothesis_and_decision_references_remain_strict() -> None:
    session, factory = prepared_session()
    visit_id = session.visits[-1].visit_id
    frozen = session.model_dump_json()
    with pytest.raises(ValueError, match="previous hypothesis"):
        record_hypothesis(
            session,
            origin_visit_id=visit_id,
            statement="Invalid revision.",
            status=HypothesisStatus.ACTIVE,
            previous_hypothesis_id="session_002_hypothesis_0001",
            id_factory=factory,
        )
    with pytest.raises(ValueError, match="information evidence"):
        record_group_decision(
            session,
            origin_visit_id=visit_id,
            decision_type=GroupDecisionType.REQUEST_INFORMATION,
            summary="Invalid evidence.",
            evidence=(EvidenceReference(information_id="foreign", relation="context"),),
            id_factory=factory,
        )
    assert session.model_dump_json() == frozen


def test_finalization_requires_no_analysis_decision_or_hypothesis() -> None:
    session, factory = prepared_session()
    provider = StaticProvider(
        '{"summary":"Direct theory","hypothesis_ids":[],"evidence":'
        '[{"information_id":"session_001_info_0001","relation":"supports"}]}'
    )

    result = finalize_lead_investigation(
        session, final_theory_provider=provider, id_factory=factory
    )

    assert result.session.status is InvestigationStatus.COMPLETED
    assert result.session.analyses == result.session.decisions == ()
    assert result.session.hypotheses == ()
    assert result.session.visits == session.visits
    assert result.session.revealed_information == session.revealed_information
    assert provider.calls[0][1] == "investigation.lead_visit.final_theory"
    with pytest.raises(ValueError, match="active session"):
        visit_lead(
            result.session, id_factory=factory, label="Late", kind="topic"
        )


@pytest.mark.parametrize(
    ("provider", "error"),
    [
        (StaticProvider("{", fail=False), StructuredOutputError),
        (StaticProvider("", fail=True), RuntimeError),
        (
            StaticProvider(
                '{"summary":"Bad","hypothesis_ids":[],"evidence":'
                '[{"information_id":"foreign","relation":"supports"}]}'
            ),
            ValueError,
        ),
    ],
)
def test_finalization_failures_are_atomic(provider: StaticProvider, error: type[Exception]) -> None:
    session, factory = prepared_session()
    frozen = session.model_dump_json()
    with pytest.raises(error):
        finalize_lead_investigation(
            session, final_theory_provider=provider, id_factory=factory
        )
    assert session.model_dump_json() == frozen
    assert session.final_theory is None


def test_mock_runtime_headline_a_b_a_workflow_is_offline_and_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import socket

    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"), session_sequence=1
    )
    session = create_session(
        id_factory=runtime.id_factory,
        introduction="A visitor vanished after midnight.",
        participant_ids=runtime.participant_ids,
    )
    session = visit_lead(
        session, id_factory=runtime.id_factory, label="A", kind="person"
    )
    lead_a = session.leads[-1].lead_id
    session = reveal_information(
        session,
        visit_id=session.visits[-1].visit_id,
        information_texts=("The window was open.",),
        id_factory=runtime.id_factory,
    )
    a1 = continue_lead_discussion(
        session,
        visit_id=session.visits[-1].visit_id,
        participant_bindings=runtime.participants,
        id_factory=runtime.id_factory,
        turn_count=runtime.capabilities.discussion_turns,
        timestamp=NOW,
    )
    session = visit_lead(
        a1.session, id_factory=runtime.id_factory, label="B", kind="location"
    )
    session = reveal_information(
        session,
        visit_id=session.visits[-1].visit_id,
        information_texts=("The corridor was used.",),
        id_factory=runtime.id_factory,
    )
    b1 = continue_lead_discussion(
        session,
        visit_id=session.visits[-1].visit_id,
        participant_bindings=runtime.participants,
        id_factory=runtime.id_factory,
        turn_count=runtime.capabilities.discussion_turns,
        timestamp=NOW,
    )
    session = visit_lead(
        b1.session, id_factory=runtime.id_factory, lead_id=lead_a
    )
    a2 = continue_lead_discussion(
        session,
        visit_id=session.visits[-1].visit_id,
        participant_bindings=runtime.participants,
        id_factory=runtime.id_factory,
        turn_count=runtime.capabilities.discussion_turns,
        timestamp=NOW,
    )
    assert "The window was open." in a2.context
    assert "The corridor was used." in a2.context
    assert a1.conversation_run.messages[0].text in a2.context
    session = visit_lead(
        a2.session, id_factory=runtime.id_factory, label="C", kind="topic"
    )
    session = visit_lead(
        session, id_factory=runtime.id_factory, label="D", kind="informant"
    )
    completed = finalize_lead_investigation(
        session,
        final_theory_provider=runtime.final_theory_provider,
        id_factory=runtime.id_factory,
    ).session

    assert completed.status is InvestigationStatus.COMPLETED
    assert [item.lead_id for item in completed.visits[:3]] == [
        lead_a, "session_001_lead_0002", lead_a
    ]
    assert len(completed.leads) == 4
    assert len(completed.visits) == 5
    assert len(completed.conversation_runs) == 3
    assert len(completed.revealed_information) == 2
    assert runtime.capabilities.available_lead_fixture_refs == (
        "lead_a", "lead_b", "lead_a_revisit"
    )
