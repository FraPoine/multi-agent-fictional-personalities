"""Playable demo content validation and state-transition regression tests."""

from pathlib import Path
import json

import pytest

from multi_agent_personalities.application import (
    DeterministicInvestigationIdFactory, complete_case_interaction,
    create_session, revisit_playable_case_lead, visit_playable_case_lead,
    ClosedGameplayNodeError, InvalidGameplayModeError,
    LockedGameplayNodeError, ManualRevealForbiddenError,
    pending_case_interaction, reveal_manual_information,
    supported_case_lead_modes,
)
from multi_agent_personalities.models import ConclusionMode, FinalTheory, InvestigationSession, InvestigationStatus
from multi_agent_personalities.case_catalog import (
    default_case_catalog_directory, load_case_catalog,
    normalize_time_code_reference, parse_supported_case_lead_reference,
)
from multi_agent_personalities.case_content_catalog import (
    default_case_content_directory, load_case_content_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_case_catalog(default_case_catalog_directory(ROOT))
CONTENT = load_case_content_catalog(default_case_content_directory(ROOT), CATALOG)


def session(case_id: str, sequence: int = 1):
    case = CATALOG.get(case_id); content = CONTENT.get(case_id)
    factory = DeterministicInvestigationIdFactory(sequence)
    mode = ConclusionMode.AUTHORED_OUTCOME if case_id == "demo-3-the-disappearance-of-a-student" else ConclusionMode.OFFICIAL_QUESTIONS
    return create_session(id_factory=factory, introduction=case.opening, participant_ids=("sherlock_holmes", "hercule_poirot"), case_id=case_id, case_content=content, conclusion_mode=mode), case, content, factory


def test_all_three_demo_content_definitions_load_without_spoilers() -> None:
    assert [(x.case_id, len(x.leads)) for x in CONTENT.cases] == [
        ("demo-1-vanishing-from-hyde-park", 18),
        ("demo-2-an-irregular-meeting", 26),
        ("demo-3-the-disappearance-of-a-student", 18),
    ]
    assert not list(default_case_content_directory(ROOT).glob("**/spoilers/*"))
    assert all("solution" not in x.model_dump_json().lower() for x in CONTENT.cases)


@pytest.mark.parametrize("raw", ("1200", " 1921 "))
def test_time_code_normalization(raw: str) -> None:
    assert normalize_time_code_reference(raw) == raw.strip()
    assert parse_supported_case_lead_reference(raw).reference_scheme == "time-code"


@pytest.mark.parametrize("raw", ("120", "12:00", "abcd", "12000"))
def test_malformed_time_codes_fail(raw: str) -> None:
    with pytest.raises(ValueError): normalize_time_code_reference(raw)


def test_first_visit_reveals_authoritative_section_once() -> None:
    current, case, content, factory = session("demo-1-vanishing-from-hyde-park")
    result = visit_playable_case_lead(current, case_definition=case, case_content=content, raw_reference="17wc", mode=None, id_factory=factory)
    assert len(result.session.revealed_information) == 1
    info = result.session.revealed_information[0]
    assert (info.source_kind, info.source_id) == ("case-section", "wc-17-s01")
    assert info.information_id in result.session.visits[0].revealed_information_ids


def test_gated_section_unlocks_on_revisit_without_duplicate() -> None:
    current, case, content, factory = session("demo-2-an-irregular-meeting")
    locked = visit_playable_case_lead(current, case_definition=case, case_content=content, raw_reference="68 WC", mode=None, id_factory=factory).session
    assert "case-gate" in {x.source_kind for x in locked.revealed_information}
    flag = visit_playable_case_lead(locked, case_definition=case, case_content=content, raw_reference="29 WC", mode=None, id_factory=factory).session
    revisited = revisit_playable_case_lead(flag, case_content=content, lead_id=locked.leads[0].lead_id, mode=None, id_factory=factory)
    assert [x.source_id for x in revisited.revealed_information].count("wc-68-s02") == 1
    assert "B" in revisited.case_state.flags


def test_explicit_choices_and_irreversible_close_are_atomic() -> None:
    current, case, content, factory = session("demo-1-vanishing-from-hyde-park")
    result = visit_playable_case_lead(current, case_definition=case, case_content=content, raw_reference="32 NW", mode=None, id_factory=factory)
    visit_id = result.session.visits[-1].visit_id
    before = result.session
    with pytest.raises(ValueError):
        complete_case_interaction(before, case_content=content, visit_id=visit_id, interaction_id="choose-floor", option_id="basement", id_factory=factory)
    assert before.case_state.choices == ()
    floor = complete_case_interaction(before, case_content=content, visit_id=visit_id, interaction_id="choose-floor", option_id="top-floor", id_factory=factory)
    attic = complete_case_interaction(floor, case_content=content, visit_id=visit_id, interaction_id="choose-top-floor-approach", option_id="attic", id_factory=factory)
    assert attic.case_state.closed_scopes == ("nw-32-top-floor",)


def test_demo3_effect_is_applied_once_not_duplicated_from_state_metadata() -> None:
    current, case, content, factory = session("demo-3-the-disappearance-of-a-student")
    result = visit_playable_case_lead(current, case_definition=case, case_content=content, raw_reference="2000", mode="interview", id_factory=factory)
    assert result.session.case_state.lead_budget_remaining == 12
    assert result.session.case_state.applied_section_ids == ("time-2000-interview-s01",)
    assert [(x.source_kind, x.amount) for x in result.session.case_state.accounting_entries] == [("variant-visit", 1), ("budget-adjustment", -3)]


def test_invalid_mode_and_locked_derived_reference_are_atomic() -> None:
    current, case, content, factory = session("demo-3-the-disappearance-of-a-student")
    before = current.model_dump(mode="python")
    with pytest.raises(InvalidGameplayModeError):
        visit_playable_case_lead(current, case_definition=case, case_content=content, raw_reference="1200", mode="investigation", id_factory=factory)
    assert current.model_dump(mode="python") == before
    with pytest.raises(LockedGameplayNodeError):
        visit_playable_case_lead(current, case_definition=case, case_content=content, raw_reference="1926", mode="interview", id_factory=factory)
    assert current.model_dump(mode="python") == before
    assert current.visits == () and current.case_state.lead_budget_remaining == 10


def test_lead_aware_mode_query_is_deterministic() -> None:
    content = CONTENT.get("demo-3-the-disappearance-of-a-student")
    assert supported_case_lead_modes(content, "time-1300") == ("interview", "investigation")
    assert supported_case_lead_modes(content, "time-1200") == ("interview",)


def test_demo1_section_cost_is_charged_once_and_closed_scope_blocks_revisit() -> None:
    current, case, content, factory = session("demo-1-vanishing-from-hyde-park")
    first = visit_playable_case_lead(current, case_definition=case, case_content=content, raw_reference="32 NW", mode=None, id_factory=factory)
    visit_id = first.session.visits[-1].visit_id
    floor = complete_case_interaction(first.session, case_content=content, visit_id=visit_id, interaction_id="choose-floor", option_id="top-floor", id_factory=factory)
    closed = complete_case_interaction(floor, case_content=content, visit_id=visit_id, interaction_id="choose-top-floor-approach", option_id="attic", id_factory=factory)
    entries = [x for x in closed.case_state.accounting_entries if x.source_kind == "section-cost"]
    assert [(x.source_id, x.amount) for x in entries] == [("nw-32-s05", 1)]
    blocked_state = closed.case_state.model_copy(update={"applied_section_ids": ("nw-32-s01",)})
    blocked = InvestigationSession.model_validate({**closed.model_dump(mode="python"), "case_state": blocked_state})
    before = blocked.model_dump(mode="python")
    with pytest.raises(ClosedGameplayNodeError):
        revisit_playable_case_lead(blocked, case_content=content, lead_id=blocked.leads[0].lead_id, mode=None, id_factory=factory)
    assert blocked.model_dump(mode="python") == before
    assert closed.revealed_information


def test_demo2_first_visits_count_but_revisit_does_not_and_wc68_order_is_correct() -> None:
    current, case, content, factory = session("demo-2-an-irregular-meeting")
    a = visit_playable_case_lead(current, case_definition=case, case_content=content, raw_reference="29 WC", mode=None, id_factory=factory).session
    lodging = visit_playable_case_lead(a, case_definition=case, case_content=content, raw_reference="68 WC", mode=None, id_factory=factory).session
    uncharged_revisit = revisit_playable_case_lead(lodging, case_content=content, lead_id=a.leads[0].lead_id, mode=None, id_factory=factory)
    assert len(uncharged_revisit.case_state.accounting_entries) == 2
    c = visit_playable_case_lead(uncharged_revisit, case_definition=case, case_content=content, raw_reference="92 WC", mode=None, id_factory=factory).session
    revisit = revisit_playable_case_lead(c, case_content=content, lead_id=lodging.leads[-1].lead_id, mode=None, id_factory=factory)
    assert len([x for x in revisit.case_state.accounting_entries if x.source_kind == "first-visit"]) == 3
    interaction = pending_case_interaction(revisit, case_content=content, visit_id=revisit.visits[-1].visit_id)
    assert interaction.interaction_id == "break-in"
    inside = complete_case_interaction(revisit, case_content=content, visit_id=revisit.visits[-1].visit_id, interaction_id="break-in", option_id=None, id_factory=factory)
    assert inside.revealed_information[-1].source_id == "wc-68-s04"
    assert "Inside, we find a pamphlet for Moby Dick" in inside.revealed_information[-1].text
    assert pending_case_interaction(inside, case_content=content, visit_id=inside.visits[-1].visit_id).interaction_id == "burn-uniform"
    assert len([x for x in inside.case_state.accounting_entries if x.source_kind == "first-visit"]) == 3


def test_authored_terminal_outcome_completes_without_final_theory_and_is_exclusive() -> None:
    current, case, content, factory = session("demo-3-the-disappearance-of-a-student")
    state = current.case_state.model_copy(update={"lead_budget_remaining": 0})
    ready = InvestigationSession.model_validate({**current.model_dump(mode="python"), "case_state": state})
    ended = visit_playable_case_lead(ready, case_definition=case, case_content=content, raw_reference="1900", mode="intervention", id_factory=factory).session
    assert ended.status is InvestigationStatus.COMPLETED
    assert ended.case_state.outcome == "mission_completed"
    assert ended.final_theory is None
    payload = ended.model_dump(mode="python")
    payload["final_theory"] = FinalTheory(final_theory_id="forbidden", summary="Conflicting theory")
    with pytest.raises(ValueError, match="mutually exclusive"):
        InvestigationSession.model_validate(payload)


def test_manual_reveal_policy_rejects_authored_case_without_mutation() -> None:
    current, case, content, factory = session("demo-1-vanishing-from-hyde-park")
    visited = visit_playable_case_lead(current, case_definition=case, case_content=content, raw_reference="17 WC", mode=None, id_factory=factory).session
    before = visited.model_dump(mode="python")
    with pytest.raises(ManualRevealForbiddenError):
        reveal_manual_information(visited, case_content=content, visit_id=visited.visits[-1].visit_id, information_texts=("not allowed",), id_factory=factory)
    assert visited.model_dump(mode="python") == before


def test_unknown_normalized_state_field_fails_strictly(tmp_path: Path) -> None:
    source = default_case_content_directory(ROOT) / "demo-1-vanishing-from-hyde-park"
    target = tmp_path / source.name
    import shutil
    shutil.copytree(source, target)
    path = target / "state.json"; data = json.loads(path.read_text()); data["duplicate_runtime_authority"] = True; path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="extra_forbidden"):
        load_case_content_catalog(tmp_path)


def test_dangling_scope_is_rejected(tmp_path: Path) -> None:
    source = default_case_content_directory(ROOT) / "demo-1-vanishing-from-hyde-park"
    target = tmp_path / source.name
    import shutil
    shutil.copytree(source, target)
    path = target / "leads" / "nw-32.json"
    data = json.loads(path.read_text())
    data["sections"][-1]["effects"][0]["scope"] = "missing-scope"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="dangling scope"):
        load_case_content_catalog(tmp_path)
