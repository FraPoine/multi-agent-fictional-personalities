"""Case-aware lead reference and visit integration tests."""

from pathlib import Path

import pytest

from multi_agent_personalities.application import (
    CurrentCaseLeadConflictError,
    DeterministicInvestigationIdFactory,
    InvalidCaseLeadReferenceError,
    UnknownCaseLeadReferenceError,
    create_session,
    resolve_case_lead,
    visit_case_lead,
    visit_lead,
)
from multi_agent_personalities.case_catalog import (
    default_case_catalog_directory,
    load_case_catalog,
    normalize_carlton_interior_reference,
    normalize_london_address_reference,
)
from multi_agent_personalities.models import FinalTheory, InvestigationStatus


ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_case_catalog(default_case_catalog_directory(ROOT))
LONDON_CASE = CATALOG.get("archive-absence")
INTERIOR_CASE = CATALOG.get("observatory-signal")


@pytest.mark.parametrize(
    "raw", ("42nw", "42NW", "42 NW", "NW42", "NW-42")
)
def test_london_aliases_normalize(raw: str) -> None:
    assert normalize_london_address_reference(raw) == "42 NW"


def test_london_reference_has_no_two_digit_maximum() -> None:
    assert normalize_london_address_reference("100sw") == "100 SW"


@pytest.mark.parametrize("raw", ("gf26", "GF26", "gf-26"))
def test_carlton_aliases_normalize(raw: str) -> None:
    assert normalize_carlton_interior_reference(raw) == "GF-26"


@pytest.mark.parametrize(
    ("normalizer", "raw"),
    (
        (normalize_london_address_reference, "42 NE"),
        (normalize_carlton_interior_reference, "LG-5"),
        (normalize_london_address_reference, "not a lead"),
    ),
)
def test_invalid_reference_structure_is_rejected(normalizer, raw: str) -> None:
    with pytest.raises(ValueError):
        normalizer(raw)


def new_case_session():
    factory = DeterministicInvestigationIdFactory(1)
    return (
        create_session(
            id_factory=factory,
            case_id=LONDON_CASE.case_id,
            introduction=LONDON_CASE.opening,
            participant_ids=("sherlock_holmes", "hercule_poirot"),
        ),
        factory,
    )


def test_resolver_distinguishes_malformed_and_unknown_references() -> None:
    assert resolve_case_lead(LONDON_CASE, "nw42").reference == "42 NW"
    with pytest.raises(InvalidCaseLeadReferenceError):
        resolve_case_lead(LONDON_CASE, "GF-26")
    with pytest.raises(UnknownCaseLeadReferenceError):
        resolve_case_lead(LONDON_CASE, "100 SW")


def test_unvisited_historical_and_explicit_revisit_preserve_identity() -> None:
    session, factory = new_case_session()
    first = visit_case_lead(
        session,
        case_definition=LONDON_CASE,
        raw_reference="42nw",
        id_factory=factory,
    )
    assert first.created is True
    assert first.lead.lead_id == "session_001_lead_0001"
    assert first.lead.case_lead_key == "archive-room"
    assert first.lead.reference == "42 NW"
    assert len(first.session.leads) == len(first.session.visits) == 1

    second = visit_case_lead(
        first.session,
        case_definition=LONDON_CASE,
        raw_reference="95 NW",
        id_factory=factory,
    )
    historical = visit_case_lead(
        second.session,
        case_definition=LONDON_CASE,
        raw_reference="NW42",
        id_factory=factory,
    )
    assert historical.created is False
    assert historical.session == second.session
    assert len(historical.session.visits) == 2

    revisited = visit_lead(
        historical.session,
        id_factory=factory,
        lead_id=historical.lead.lead_id,
    )
    assert len(revisited.visits) == 3
    assert revisited.visits[-1].lead_id == first.lead.lead_id
    assert revisited.leads[0].reference == "42 NW"


def test_already_current_and_completed_sessions_are_rejected() -> None:
    session, factory = new_case_session()
    current = visit_case_lead(
        session,
        case_definition=LONDON_CASE,
        raw_reference="42 NW",
        id_factory=factory,
    )
    with pytest.raises(CurrentCaseLeadConflictError):
        visit_case_lead(
            current.session,
            case_definition=LONDON_CASE,
            raw_reference="42 NW",
            id_factory=factory,
        )
    completed = current.session.model_copy(
        update={
            "status": InvestigationStatus.COMPLETED,
            "final_theory": FinalTheory(
                final_theory_id="session_001_final_theory",
                summary="The synthetic case is concluded.",
            ),
        }
    )
    with pytest.raises(ValueError, match="active session"):
        visit_case_lead(
            completed,
            case_definition=LONDON_CASE,
            raw_reference="95 NW",
            id_factory=factory,
        )
