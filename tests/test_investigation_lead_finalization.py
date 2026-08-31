"""Optional reasoning and explicit finalization for Lead/Visit sessions."""

from datetime import datetime, timezone

import pytest

from multi_agent_personalities.application import (
    DeterministicInvestigationIdFactory,
    StructuredOutputError,
    build_investigation_mock_runtime,
    build_lead_discussion_context,
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
    InvestigationSession,
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


def test_historical_visits_reject_new_activity_and_revisit_accepts_it() -> None:
    session, factory = prepared_session()
    lead_a = session.leads[0].lead_id
    historical_visit_id = session.visits[0].visit_id
    session = visit_lead(
        session, id_factory=factory, label="Lead B", kind="location"
    )
    frozen = session.model_dump_json()
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"), session_sequence=1
    )
    historical_context = build_lead_discussion_context(
        session, visit_id=historical_visit_id
    )
    assert "Lead A" in historical_context
    assert "The window was open." in historical_context

    operations = (
        lambda: reveal_information(
            session,
            visit_id=historical_visit_id,
            information_texts=("Retroactive information.",),
            id_factory=factory,
        ),
        lambda: continue_lead_discussion(
            session,
            visit_id=historical_visit_id,
            participant_bindings=runtime.participants,
            id_factory=factory,
            turn_count=2,
            timestamp=NOW,
        ),
        lambda: record_visit_analysis(
            session,
            visit_id=historical_visit_id,
            agent_id="sherlock_holmes",
            facts=("Retroactive analysis.",),
            id_factory=factory,
        ),
        lambda: record_hypothesis(
            session,
            origin_visit_id=historical_visit_id,
            statement="Retroactive hypothesis.",
            status=HypothesisStatus.ACTIVE,
            id_factory=factory,
        ),
        lambda: record_group_decision(
            session,
            origin_visit_id=historical_visit_id,
            decision_type=GroupDecisionType.REQUEST_INFORMATION,
            summary="Retroactive decision.",
            id_factory=factory,
        ),
    )
    for operation in operations:
        with pytest.raises(ValueError, match="current latest visit"):
            operation()
        assert session.model_dump_json() == frozen

    session = visit_lead(session, id_factory=factory, lead_id=lead_a)
    current_visit_id = session.visits[-1].visit_id
    session = reveal_information(
        session,
        visit_id=current_visit_id,
        information_texts=("Current revisit information.",),
        id_factory=factory,
    )
    discussed = continue_lead_discussion(
        session,
        visit_id=current_visit_id,
        participant_bindings=runtime.participants,
        id_factory=factory,
        turn_count=2,
        timestamp=NOW,
    )
    session = record_visit_analysis(
        discussed.session,
        visit_id=current_visit_id,
        agent_id="sherlock_holmes",
        facts=("Current analysis.",),
        id_factory=factory,
    )
    session = record_hypothesis(
        session,
        origin_visit_id=current_visit_id,
        statement="Current hypothesis.",
        status=HypothesisStatus.ACTIVE,
        evidence=(info_ref(3),),
        id_factory=factory,
    )
    session = record_group_decision(
        session,
        origin_visit_id=current_visit_id,
        decision_type=GroupDecisionType.PURSUE_LEAD,
        summary="Current decision.",
        hypothesis_ids=(session.hypotheses[-1].hypothesis_id,),
        evidence=(info_ref(3),),
        id_factory=factory,
    )

    assert session.visits[0].revealed_information_ids == (
        "session_001_info_0001", "session_001_info_0002"
    )
    assert session.visits[-1].revealed_information_ids == (
        "session_001_info_0003",
    )
    assert session.visits[-1].conversation_run_ids == (
        "session_001_visit_0003_discussion_0001",
    )


def test_visit_hypothesis_revision_respects_visit_chronology() -> None:
    session, factory = prepared_session()
    visit_one = session.visits[-1].visit_id
    session = record_hypothesis(
        session,
        origin_visit_id=visit_one,
        statement="First hypothesis.",
        status=HypothesisStatus.ACTIVE,
        id_factory=factory,
    )
    first_id = session.hypotheses[-1].hypothesis_id
    session = visit_lead(
        session, id_factory=factory, label="Lead B", kind="location"
    )
    session = record_hypothesis(
        session,
        origin_visit_id=session.visits[-1].visit_id,
        statement="Later revision.",
        status=HypothesisStatus.ACTIVE,
        previous_hypothesis_id=first_id,
        id_factory=factory,
    )
    assert session.hypotheses[-1].previous_hypothesis_id == first_id

    payload = session.model_dump(mode="python")
    payload["hypotheses"] = (
        {
            "hypothesis_id": "session_001_hypothesis_0001",
            "session_id": "session_001",
            "origin_visit_id": "session_001_visit_0002",
            "statement": "Later-origin hypothesis.",
            "status": "active",
        },
        {
            "hypothesis_id": "session_001_hypothesis_0002",
            "session_id": "session_001",
            "origin_visit_id": "session_001_visit_0001",
            "statement": "Invalid earlier-origin revision.",
            "status": "active",
            "previous_hypothesis_id": "session_001_hypothesis_0001",
        },
    )
    with pytest.raises(ValueError, match="later visit"):
        InvestigationSession.model_validate(payload)


def test_real_mock_runtime_supports_two_segments_on_current_visit(
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
        introduction="Repeatable discussion case.",
        participant_ids=runtime.participant_ids,
    )
    session = visit_lead(
        session, id_factory=runtime.id_factory, label="A", kind="person"
    )
    session = reveal_information(
        session,
        visit_id=session.visits[-1].visit_id,
        information_texts=("A fact.",),
        id_factory=runtime.id_factory,
    )
    first = continue_lead_discussion(
        session,
        visit_id=session.visits[-1].visit_id,
        participant_bindings=runtime.participants,
        id_factory=runtime.id_factory,
        turn_count=2,
        timestamp=NOW,
    )
    frozen_first = first.conversation_run.model_dump_json()
    second = continue_lead_discussion(
        first.session,
        visit_id=first.session.visits[-1].visit_id,
        participant_bindings=runtime.participants,
        id_factory=runtime.id_factory,
        turn_count=2,
        timestamp=NOW,
    )

    assert first.conversation_run.run_id.endswith("discussion_0001")
    assert second.conversation_run.run_id.endswith("discussion_0002")
    assert first.conversation_run.model_dump_json() == frozen_first
    assert second.session.visits[-1].conversation_run_ids == (
        first.conversation_run.run_id,
        second.conversation_run.run_id,
    )
    assert runtime.capabilities.available_discussion_segments == 4
