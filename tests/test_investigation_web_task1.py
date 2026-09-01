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
    assert "Open a new case" in response.text
    assert "The Archive Absence" in response.text
    assert "The Observatory Signal" in response.text
    assert 'name="case_id"' in response.text
    assert 'name="introduction"' not in response.text
    assert "Select investigators" in response.text
    assert "Sherlock Holmes" in response.text
    assert "Hercule Poirot" in response.text
    assert "Start investigation" in response.text
    assert "Read rules" in response.text
    assert "reproduce a commercial rulebook" in response.text
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
    assert "Case opening" in response.text
    assert "The investigation begins" in response.text
    assert DEMO_CASE.opening in response.text
    assert "Sherlock Holmes" in response.text
    assert "Hercule Poirot" in response.text
    assert "Resources" in response.text
    assert "Review the immutable case briefing." in response.text
    assert "Rules" in response.text
    assert "Begin investigation" in response.text
    assert "No leads visited yet" in response.text
    for legacy in (
        "Reveal clue",
        "Run independent analyses",
        "Run group discussion",
        "Create group decision",
        "Workflow state",
        "Round status",
    ):
        assert legacy not in response.text
