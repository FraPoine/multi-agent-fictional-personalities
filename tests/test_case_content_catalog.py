"""Playable demo content validation and state-transition regression tests."""

from pathlib import Path
import json

import pytest

from multi_agent_personalities.application import (
    DeterministicInvestigationIdFactory, complete_case_interaction,
    create_session, revisit_playable_case_lead, visit_playable_case_lead,
)
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
    return create_session(id_factory=factory, introduction=case.opening, participant_ids=("sherlock_holmes", "hercule_poirot"), case_id=case_id, case_content=content), case, content, factory


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
