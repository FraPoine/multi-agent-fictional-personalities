"""Focused contract tests for the Lead/Visit investigation foundation."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models import (
    EvidenceReference,
    FinalTheory,
    InvestigationLead,
    InvestigationSession,
    InvestigationStatus,
    LeadVisit,
    RevealedInformation,
)


SESSION_ID = "session_001"


def lead(index: int, *, session_id: str = SESSION_ID) -> dict[str, object]:
    return {
        "lead_id": f"{session_id}_lead_{index:04d}",
        "session_id": session_id,
        "label": f"Lead {index}",
        "kind": "topic",
    }


def visit(
    index: int,
    lead_index: int,
    *,
    information_indexes: tuple[int, ...] = (),
    session_id: str = SESSION_ID,
) -> dict[str, object]:
    return {
        "visit_id": f"{session_id}_visit_{index:04d}",
        "session_id": session_id,
        "lead_id": f"{session_id}_lead_{lead_index:04d}",
        "visit_index": index,
        "revealed_information_ids": [
            f"{session_id}_info_{item:04d}" for item in information_indexes
        ],
        "conversation_run_ids": [],
    }


def information(
    index: int,
    *,
    lead_index: int | None = None,
    visit_index: int | None = None,
    session_id: str = SESSION_ID,
) -> dict[str, object]:
    return {
        "information_id": f"{session_id}_info_{index:04d}",
        "session_id": session_id,
        "text": f"Revealed information {index}.",
        "reveal_index": index - 1,
        "lead_id": (
            f"{session_id}_lead_{lead_index:04d}"
            if lead_index is not None
            else None
        ),
        "visit_id": (
            f"{session_id}_visit_{visit_index:04d}"
            if visit_index is not None
            else None
        ),
    }


def session_payload() -> dict[str, object]:
    return {
        "session_id": SESSION_ID,
        "case_introduction": "A compact case opening.",
        "participant_ids": ["detective_a", "detective_b"],
        "status": "active",
        "leads": [],
        "visits": [],
        "revealed_information": [],
    }


def test_new_domain_records_are_frozen_and_strict() -> None:
    item = InvestigationLead.model_validate(lead(1))
    visit_item = LeadVisit.model_validate(visit(1, 1))
    info = RevealedInformation.model_validate(information(1))

    with pytest.raises(ValidationError):
        InvestigationLead.model_validate({**lead(1), "unexpected": True})
    with pytest.raises(ValidationError):
        visit_item.visit_index = 2
    with pytest.raises(ValidationError):
        info.text = "changed"
    assert item.label == "Lead 1"
    assert item.custom_label is None
    renamed = InvestigationLead.model_validate(
        {**lead(1), "custom_label": "  House of Lestrade  "}
    )
    assert renamed.custom_label == "House of Lestrade"
    with pytest.raises(ValidationError):
        InvestigationLead.model_validate({**lead(1), "custom_label": " "})


def test_duplicate_and_foreign_leads_are_rejected() -> None:
    payload = session_payload()
    payload["leads"] = [lead(1), lead(1)]
    with pytest.raises(ValidationError, match="lead_id values must be unique"):
        InvestigationSession.model_validate(payload)

    payload["leads"] = [lead(1, session_id="session_002")]
    with pytest.raises(ValidationError, match="all leads must belong"):
        InvestigationSession.model_validate(payload)


def test_arbitrary_lead_count_is_allowed() -> None:
    payload = session_payload()
    payload["leads"] = [lead(index) for index in range(1, 31)]
    assert len(InvestigationSession.model_validate(payload).leads) == 30


def test_duplicate_foreign_unknown_and_misordered_visits_are_rejected() -> None:
    payload = session_payload()
    payload["leads"] = [lead(1)]
    payload["visits"] = [visit(1, 1), visit(1, 1)]
    with pytest.raises(ValidationError, match="visit_id values must be unique"):
        InvestigationSession.model_validate(payload)

    payload["visits"] = [visit(1, 2)]
    with pytest.raises(ValidationError, match="unknown lead"):
        InvestigationSession.model_validate(payload)

    payload["visits"] = [{**visit(1, 1), "session_id": "session_002"}]
    with pytest.raises(ValidationError, match="all visits must belong"):
        InvestigationSession.model_validate(payload)

    payload["visits"] = [visit(2, 1), visit(1, 1)]
    with pytest.raises(ValidationError, match="visit_index"):
        InvestigationSession.model_validate(payload)


def test_a_b_a_c_a_is_valid_without_reasoning_or_visit_statuses() -> None:
    payload = session_payload()
    payload["leads"] = [lead(index) for index in range(1, 4)]
    payload["visits"] = [
        visit(1, 1),
        visit(2, 2),
        visit(3, 1),
        visit(4, 3),
        visit(5, 1),
    ]

    session = InvestigationSession.model_validate(payload)

    assert [item.lead_id for item in session.visits] == [
        "session_001_lead_0001",
        "session_001_lead_0002",
        "session_001_lead_0001",
        "session_001_lead_0003",
        "session_001_lead_0001",
    ]
    assert session.analyses == session.hypotheses == session.decisions == ()
    assert "status" not in LeadVisit.model_fields


def test_arbitrary_visit_count_is_allowed() -> None:
    payload = session_payload()
    payload["leads"] = [lead(1)]
    payload["visits"] = [visit(index, 1) for index in range(1, 31)]
    assert len(InvestigationSession.model_validate(payload).visits) == 30


def test_multiple_information_items_can_belong_to_one_lead_and_visit() -> None:
    payload = session_payload()
    payload["leads"] = [lead(1)]
    payload["visits"] = [visit(1, 1, information_indexes=(1, 2, 3))]
    payload["revealed_information"] = [
        information(index, lead_index=1, visit_index=1)
        for index in range(1, 4)
    ]

    session = InvestigationSession.model_validate(payload)

    assert len(session.revealed_information) == 3
    assert session.visits[0].revealed_information_ids == (
        "session_001_info_0001",
        "session_001_info_0002",
        "session_001_info_0003",
    )


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("duplicate", "information_id values must be unique"),
        ("foreign_session", "all revealed information must belong"),
        ("unknown_lead", "unknown lead"),
        ("unknown_visit", "unknown visit"),
        ("wrong_visit_lead", "does not match its visit lead"),
    ],
)
def test_invalid_information_ownership_and_sources_are_rejected(
    mutation: str, message: str
) -> None:
    payload = session_payload()
    payload["leads"] = [lead(1), lead(2)]
    payload["visits"] = [visit(1, 1, information_indexes=(1,))]
    payload["revealed_information"] = [information(1, lead_index=1, visit_index=1)]
    if mutation == "duplicate":
        payload["revealed_information"] = [
            information(1, lead_index=1, visit_index=1),
            {**information(1, lead_index=1, visit_index=1), "reveal_index": 1},
        ]
    elif mutation == "foreign_session":
        payload["revealed_information"][0]["session_id"] = "session_002"  # type: ignore[index]
    elif mutation == "unknown_lead":
        payload["revealed_information"][0]["lead_id"] = "missing"  # type: ignore[index]
    elif mutation == "unknown_visit":
        payload["revealed_information"][0]["visit_id"] = "missing"  # type: ignore[index]
    else:
        payload["revealed_information"][0]["lead_id"] = "session_001_lead_0002"  # type: ignore[index]

    with pytest.raises(ValidationError, match=message):
        InvestigationSession.model_validate(payload)


def test_evidence_uses_information_ids_and_unknown_information_is_rejected() -> None:
    reference = EvidenceReference(
        information_id="session_001_info_0001", relation="supports"
    )
    assert reference.information_id == "session_001_info_0001"
    assert reference.clue_id is None

    payload = session_payload()
    payload["status"] = InvestigationStatus.COMPLETED
    payload["final_theory"] = FinalTheory(
        final_theory_id="session_001_final_theory",
        summary="A theory.",
        evidence=(reference,),
    )
    with pytest.raises(ValidationError, match="information evidence"):
        InvestigationSession.model_validate(payload)

    payload["revealed_information"] = [information(1)]
    assert InvestigationSession.model_validate(payload).final_theory is not None


def test_visit_linkage_is_explicit_and_bidirectional() -> None:
    payload = session_payload()
    payload["leads"] = [lead(1)]
    payload["visits"] = [visit(1, 1)]
    payload["revealed_information"] = [information(1, lead_index=1, visit_index=1)]
    with pytest.raises(ValidationError, match="must be listed by its visit"):
        InvestigationSession.model_validate(payload)

    mismatched = deepcopy(payload)
    mismatched["visits"][0]["revealed_information_ids"] = ["session_001_info_0001"]  # type: ignore[index]
    mismatched["revealed_information"][0]["visit_id"] = None  # type: ignore[index]
    with pytest.raises(ValidationError, match="must match information visit_id"):
        InvestigationSession.model_validate(mismatched)
