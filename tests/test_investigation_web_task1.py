"""Sprint 7 Lead/Visit UX redesign Task 1 web checks."""

from pathlib import Path

import pytest

from multi_agent_personalities.models import InvestigationStatus
from multi_agent_personalities.web.app import create_app
from multi_agent_personalities.web.investigation_store import InMemoryInvestigationRegistry
from multi_agent_personalities.case_catalog import (
    default_case_catalog_directory,
    load_case_catalog,
)
from tests.asgi_client import ASGITestClient


ROOT = Path(__file__).resolve().parents[1]
DEMO_CASE = load_case_catalog(default_case_catalog_directory(ROOT)).cases[0]
VALID_FORM = {
    "characters": ["sherlock", "poirot"],
    "case_id": "archive-absence",
}


@pytest.fixture
def task1_client(tmp_path: Path):
    registry = InMemoryInvestigationRegistry()
    app = create_app(
        project_root=ROOT,
        output_root=tmp_path / "outputs",
        investigation_registry=registry,
    )
    with ASGITestClient(app) as client:
        yield client, registry


def test_lobby_is_catalogue_backed_game_start(task1_client) -> None:
    client, registry = task1_client

    response = client.get("/investigations")

    assert response.status_code == 200
    assert registry.session_ids == ()
    assert "New Investigation" in response.text
    assert "Configure your case and investigator team before beginning." in response.text
    assert "The Archive Absence" in response.text
    assert "The Observatory Signal" in response.text
    assert 'name="case_id"' in response.text
    assert 'value="archive-absence"' in response.text
    assert 'value="observatory-signal"' in response.text
    assert 'name="introduction"' not in response.text
    assert "Investigators" in response.text
    assert "Select at least two investigators to begin." in response.text
    assert 'aria-describedby="investigator-requirement' in response.text
    assert "Sherlock Holmes" in response.text
    assert "Hercule Poirot" in response.text
    assert "Analytical, observational, and deductive." in response.text
    assert "Methodical, psychological, and orderly." in response.text
    assert '<legend class="visually-hidden">Investigators</legend>' in response.text
    assert '<h2 id="investigator-selection-title">Investigators</h2>' in response.text
    assert 'name="characters" value="sherlock"' in response.text
    assert 'name="characters" value="poirot"' in response.text
    assert "investigator-avatar participant-tone-1" in response.text
    assert "investigator-avatar participant-tone-2" in response.text
    assert "Start Investigation" in response.text
    assert "Read Rules" in response.text
    assert "data-investigation-lobby-form" in response.text
    assert 'data-min-investigators="2"' in response.text
    assert 'data-required-investigator-count="2"' in response.text
    assert "data-investigation-start>Start Investigation" in response.text
    assert "data-investigation-start disabled" not in response.text
    assert "Demo Case" not in response.text
    assert "Case Library" not in response.text
    assert "reproduce a commercial rulebook" in response.text
    assert '>Conversations</a>' in response.text
    assert 'aria-current="page">Investigations</a>' in response.text
    assert 'aria-current="page">Conversations</a>' not in response.text
    for legacy in ("Reveal clue", "Independent analyses", "Group decision"):
        assert legacy not in response.text


def test_invalid_creation_preserves_values_without_registration(task1_client) -> None:
    client, registry = task1_client
    response = client.post(
        "/investigations",
        data={"characters": ["sherlock"], "case_id": "observatory-signal"},
    )

    assert response.status_code == 400
    assert registry.session_ids == ()
    assert 'value="observatory-signal" checked' in response.text
    assert 'value="sherlock" checked' in response.text
    assert "Select all supported investigators" in response.text
    assert 'data-investigation-start disabled aria-disabled="true"' in response.text


def test_creation_registers_authoritative_empty_lead_visit_session(task1_client) -> None:
    client, registry = task1_client

    response = client.post("/investigations", data=VALID_FORM)

    assert response.status_code == 303
    assert response.headers["location"] == "/investigations/session_001"
    assert registry.session_ids == ("session_001",)
    session = registry.snapshot("session_001")
    assert session.status is InvestigationStatus.ACTIVE
    assert session.case_id == DEMO_CASE.case_id
    assert session.case_introduction == DEMO_CASE.opening
    assert session.leads == ()
    assert session.visits == ()


def test_selected_case_supplies_trusted_opening(task1_client) -> None:
    client, registry = task1_client
    catalog = load_case_catalog(default_case_catalog_directory(ROOT))
    selected = catalog.get("observatory-signal")

    response = client.post(
        "/investigations",
        data={
            "characters": ["sherlock", "poirot"],
            "case_id": selected.case_id,
            "introduction": "Browser-supplied text must be ignored.",
        },
    )

    assert response.status_code == 303
    session = registry.snapshot("session_001")
    assert session.case_id == selected.case_id
    assert session.case_introduction == selected.opening
    assert "Browser-supplied text" not in session.case_introduction


def test_unknown_case_is_404_and_atomic(task1_client) -> None:
    client, registry = task1_client

    response = client.post(
        "/investigations",
        data={
            "characters": ["sherlock", "poirot"],
            "case_id": "missing-case",
        },
    )

    assert response.status_code == 404
    assert registry.session_ids == ()


def test_case_opening_shell_is_side_effect_free(task1_client) -> None:
    client, registry = task1_client
    client.post("/investigations", data=VALID_FORM)
    before = registry.snapshot("session_001")

    response = client.get("/investigations/session_001")

    assert response.status_code == 200
    assert registry.snapshot("session_001") == before
    assert response.text.count('class="case-file-card"') == 1
    assert '<header class="case-file-header">' in response.text
    assert DEMO_CASE.title in response.text
    assert DEMO_CASE.short_description in response.text
    assert "Case opening" in response.text
    assert "The investigation begins" not in response.text
    assert DEMO_CASE.opening in response.text
    assert "Sherlock Holmes" in response.text
    assert "Hercule Poirot" in response.text
    assert "A fictional consulting detective known for acute observation" not in response.text
    assert "A fictional Belgian private detective known for psychological insight" not in response.text
    assert '<button class="primary-action begin-investigating" type="button" data-begin-investigating>Begin Investigating</button>' in response.text
    assert '<header class="case-bar">' not in response.text
    assert "Resources" in response.text
    assert 'aria-label="Case Opening"' in response.text
    assert "Rules" in response.text
    assert "No leads visited yet" in response.text
    assert 'data-leads-toggle aria-controls="lead-panel" aria-expanded="false"' in response.text
    assert 'data-resource-drawer role="dialog" aria-modal="true"' in response.text
    assert '>Conversations</a>' in response.text
    assert 'aria-current="page">Investigations</a>' in response.text
    for legacy in (
        "Reveal clue",
        "Run independent analyses",
        "Run group discussion",
        "Create group decision",
        "Workflow state",
        "Round status",
    ):
        assert legacy not in response.text
