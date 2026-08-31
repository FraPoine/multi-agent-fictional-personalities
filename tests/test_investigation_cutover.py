"""Final architectural cutover and isolation contract."""

from multi_agent_personalities import application, models
from multi_agent_personalities.application import (
    DeterministicInvestigationIdFactory,
    create_session,
    record_group_decision,
    record_hypothesis,
    reveal_information,
    visit_lead,
)
from multi_agent_personalities.models import (
    EvidenceReference,
    GroupDecisionType,
    HypothesisStatus,
)


def test_authoritative_exports_exclude_round_gameplay_contract() -> None:
    assert set(application.LEGACY_ROUND_APPLICATION_NAMES).isdisjoint(
        application.__all__
    )
    assert set(models.LEGACY_ROUND_MODEL_NAMES).isdisjoint(models.__all__)
    assert {
        "create_session",
        "visit_lead",
        "reveal_information",
        "continue_lead_discussion",
        "finalize_lead_investigation",
    } <= set(application.__all__)


def test_interleaved_sessions_isolate_leads_information_and_reasoning() -> None:
    first_factory = DeterministicInvestigationIdFactory(1)
    second_factory = DeterministicInvestigationIdFactory(2)
    first = create_session(
        id_factory=first_factory,
        introduction="First opening.",
        participant_ids=("alpha", "beta"),
    )
    second = create_session(
        id_factory=second_factory,
        introduction="Second opening.",
        participant_ids=("alpha", "beta"),
    )
    first = visit_lead(
        first, id_factory=first_factory, label="A", kind="person"
    )
    first_a = first.leads[-1].lead_id
    second = visit_lead(
        second, id_factory=second_factory, label="X", kind="location"
    )
    first = reveal_information(
        first,
        visit_id=first.visits[-1].visit_id,
        information_texts=("First-only fact.",),
        id_factory=first_factory,
    )
    second = reveal_information(
        second,
        visit_id=second.visits[-1].visit_id,
        information_texts=("Second-only fact.",),
        id_factory=second_factory,
    )
    first = visit_lead(
        first, id_factory=first_factory, label="B", kind="topic"
    )
    second = visit_lead(
        second, id_factory=second_factory, label="Y", kind="informant"
    )
    first = visit_lead(first, id_factory=first_factory, lead_id=first_a)
    first = record_hypothesis(
        first,
        origin_visit_id=first.visits[-1].visit_id,
        statement="A session-one hypothesis.",
        status=HypothesisStatus.ACTIVE,
        evidence=(
            EvidenceReference(
                information_id="session_001_info_0001",
                relation="supports",
            ),
        ),
        id_factory=first_factory,
    )
    second = record_group_decision(
        second,
        origin_visit_id=second.visits[-1].visit_id,
        decision_type=GroupDecisionType.REQUEST_INFORMATION,
        summary="A session-two decision.",
        evidence=(
            EvidenceReference(
                information_id="session_002_info_0001",
                relation="context",
            ),
        ),
        id_factory=second_factory,
    )

    assert [item.label for item in first.leads] == ["A", "B"]
    assert [item.label for item in second.leads] == ["X", "Y"]
    assert [item.text for item in first.revealed_information] == [
        "First-only fact."
    ]
    assert [item.text for item in second.revealed_information] == [
        "Second-only fact."
    ]
    assert len(first.hypotheses) == 1 and second.hypotheses == ()
    assert first.decisions == () and len(second.decisions) == 1
    assert all(
        item.session_id.startswith("session_001") for item in first.leads
    )
    assert all(
        item.session_id.startswith("session_002") for item in second.leads
    )
