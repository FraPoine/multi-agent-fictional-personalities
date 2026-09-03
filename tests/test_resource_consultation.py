"""Atomic explicit resource consultation and prompt-boundary regressions."""

from pathlib import Path

import pytest

from multi_agent_personalities.application import (
    ConsultationClosedError, ConsultationConflictError, DeterministicAnswerDraftProvider,
    DeterministicInvestigationIdFactory, PlayerOnlyResourceError,
    UnknownConsultationResourceError, build_lead_discussion_context,
    build_safe_answer_context, consult_case_resource, create_session,
    generate_official_answer_drafts, start_official_conclusion,
    visit_playable_case_lead,
)
from multi_agent_personalities.case_catalog import default_case_catalog_directory, load_case_catalog
from multi_agent_personalities.case_content_catalog import default_case_content_directory, load_case_content_catalog
from multi_agent_personalities.conclusion_catalog import default_public_conclusion_directory, load_public_conclusion_catalog
from multi_agent_personalities.models import ConclusionMode, FinalTheory, InvestigationSession, InvestigationStatus
from multi_agent_personalities.resource_text_catalog import default_resource_text_directory, load_resource_text_catalog


ROOT = Path(__file__).resolve().parents[1]
CASES = load_case_catalog(default_case_catalog_directory(ROOT))
CONTENT = load_case_content_catalog(default_case_content_directory(ROOT), CASES)
PUBLIC = load_public_conclusion_catalog(default_public_conclusion_directory(ROOT), CASES)
RESOURCES = load_resource_text_catalog(default_resource_text_directory(ROOT), CASES)
CASE_ID = "demo-1-vanishing-from-hyde-park"
DIRECTORY_ID = f"{CASE_ID}-directory"
NEWSPAPER_ID = f"{CASE_ID}-newspaper"


def session():
    factory = DeterministicInvestigationIdFactory(1)
    case = CASES.get(CASE_ID)
    current = create_session(
        id_factory=factory, introduction=case.opening,
        participant_ids=("sherlock_holmes", "hercule_poirot"),
        case_id=CASE_ID, case_content=CONTENT.get(CASE_ID),
        conclusion_mode=ConclusionMode.OFFICIAL_QUESTIONS,
    )
    return current, case, factory


def test_viewing_structural_asset_does_not_consult_but_explicit_operation_does() -> None:
    current, _case, _factory = session()
    assert CASES.resources_for_case(CASE_ID)
    assert current.resource_consultations == ()
    consulted = consult_case_resource(current, resource_id=DIRECTORY_ID, case_catalog=CASES, resource_text_catalog=RESOURCES)
    assert current.resource_consultations == ()
    assert [(item.resource_id, item.consultation_index) for item in consulted.resource_consultations] == [(DIRECTORY_ID, 0)]
    repeated = consult_case_resource(consulted, resource_id=DIRECTORY_ID, case_catalog=CASES, resource_text_catalog=RESOURCES)
    assert repeated == consulted


@pytest.mark.parametrize("resource_id", ("unknown", "demo-2-an-irregular-meeting-directory"))
def test_unknown_and_cross_case_consultation_fail_atomically(resource_id: str) -> None:
    current, _case, _factory = session(); before = current.model_dump_json()
    with pytest.raises(UnknownConsultationResourceError):
        consult_case_resource(current, resource_id=resource_id, case_catalog=CASES, resource_text_catalog=RESOURCES)
    assert current.model_dump_json() == before


def test_player_only_map_fails_atomically() -> None:
    current, _case, _factory = session(); before = current.model_dump_json()
    with pytest.raises(PlayerOnlyResourceError):
        consult_case_resource(current, resource_id=f"{CASE_ID}-map", case_catalog=CASES, resource_text_catalog=RESOURCES)
    assert current.model_dump_json() == before


def test_only_consulted_resource_enters_discussion_and_answer_context_and_persists() -> None:
    current, case, factory = session()
    consulted = consult_case_resource(current, resource_id=DIRECTORY_ID, case_catalog=CASES, resource_text_catalog=RESOURCES)
    visited = visit_playable_case_lead(
        consulted, case_definition=case, case_content=CONTENT.get(CASE_ID),
        raw_reference="17 WC", mode=None, id_factory=factory,
    ).session
    discussion = build_lead_discussion_context(
        visited, visit_id=visited.visits[-1].visit_id, resource_text_catalog=RESOURCES,
    )
    assert "Hennessy, Patrick — 37 WC" in discussion
    assert "SCANDAL AT THE PARLIAMENT" not in discussion
    ready = start_official_conclusion(visited, public_definition=PUBLIC.get(CASE_ID))
    answer_context = build_safe_answer_context(ready, public_definition=PUBLIC.get(CASE_ID), resource_text_catalog=RESOURCES)
    assert "Hennessy, Patrick — 37 WC" in answer_context
    assert "SCANDAL AT THE PARLIAMENT" not in answer_context
    assert "Howard Parker (30 points)" not in answer_context
    assert tuple(item.resource_id for item in visited.resource_consultations) == (DIRECTORY_ID,)


def test_draft_provider_failure_with_consulted_context_is_atomic() -> None:
    current, _case, _factory = session()
    consulted = consult_case_resource(current, resource_id=NEWSPAPER_ID, case_catalog=CASES, resource_text_catalog=RESOURCES)
    ready = start_official_conclusion(consulted, public_definition=PUBLIC.get(CASE_ID)); before = ready.model_dump_json()
    provider = DeterministicAnswerDraftProvider({"q1": "only one"})
    with pytest.raises(ValueError):
        generate_official_answer_drafts(ready, public_definition=PUBLIC.get(CASE_ID), provider=provider, resource_text_catalog=RESOURCES)
    assert ready.model_dump_json() == before


def test_completed_session_is_readable_but_rejects_consultation() -> None:
    current, _case, _factory = session()
    consulted = consult_case_resource(current, resource_id=DIRECTORY_ID, case_catalog=CASES, resource_text_catalog=RESOURCES)
    legacy = consulted.model_copy(update={"conclusion_mode": ConclusionMode.GENERATED_FINAL_THEORY})
    completed = InvestigationSession.model_validate({
        **legacy.model_dump(mode="python"),
        "status": InvestigationStatus.COMPLETED,
        "final_theory": FinalTheory(final_theory_id="final", summary="Complete."),
    })
    assert "Hennessy, Patrick — 37 WC" in build_safe_answer_context(
        completed,
        public_definition=PUBLIC.get(CASE_ID),
        resource_text_catalog=RESOURCES,
    )
    before = completed.model_dump_json()
    with pytest.raises(ConsultationClosedError):
        consult_case_resource(completed, resource_id=DIRECTORY_ID, case_catalog=CASES, resource_text_catalog=RESOURCES)
    assert completed.model_dump_json() == before


def test_ready_for_final_rejects_consultation_atomically() -> None:
    current, _case, _factory = session()
    ready = start_official_conclusion(current, public_definition=PUBLIC.get(CASE_ID))
    before = ready.model_dump_json()
    with pytest.raises(ConsultationConflictError):
        consult_case_resource(ready, resource_id=DIRECTORY_ID, case_catalog=CASES, resource_text_catalog=RESOURCES)
    assert ready.model_dump_json() == before
