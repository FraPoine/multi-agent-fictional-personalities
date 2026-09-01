"""Sprint 7 Lead/Visit UX redesign Task 3 web checks."""

from pathlib import Path

import pytest

import multi_agent_personalities.web.investigation_routes as routes
from multi_agent_personalities.case_catalog import (
    default_case_catalog_directory,
    load_case_catalog,
)
from multi_agent_personalities.models import InvestigationStatus
from multi_agent_personalities.web.app import create_app
from multi_agent_personalities.web.investigation_store import (
    InMemoryInvestigationRegistry,
)
from tests.asgi_client import ASGITestClient


ROOT = Path(__file__).resolve().parents[1]
CASE_OPENING = load_case_catalog(default_case_catalog_directory(ROOT)).cases[0].opening
INTRODUCTION = "A coded letter arrives without a sender."


@pytest.fixture
def task3_client(tmp_path: Path):
    registry = InMemoryInvestigationRegistry()
    app = create_app(
        project_root=ROOT,
        output_root=tmp_path / "outputs",
        investigation_registry=registry,
    )
    with ASGITestClient(app) as client:
        client.post(
            "/investigations",
            data={
                "characters": ["sherlock", "poirot"],
                "introduction": INTRODUCTION,
            },
        )
        yield client, registry


def prepare_finalizable(
    client: ASGITestClient,
    registry: InMemoryInvestigationRegistry,
):
    client.post(
        "/investigations/session_001/leads",
        data={"reference": "42 NW"},
    )
    visit = registry.snapshot("session_001").visits[-1]
    for text in ("The window was open.", "The corridor was used."):
        response = client.post(
            f"/investigations/session_001/visits/{visit.visit_id}/information",
            data={"information": text},
        )
        assert response.status_code == 303
    return visit


def test_resource_drawer_is_honest_and_human_composer_is_disabled(
    task3_client,
) -> None:
    client, registry = task3_client
    prepare_finalizable(client, registry)

    page = client.get("/investigations/session_001")

    assert page.status_code == 200
    assert 'data-resource-drawer' in page.text
    assert 'data-resource-open="case-opening"' in page.text
    assert 'data-resource-open="rules"' in page.text
    assert CASE_OPENING in page.text
    for resource in (
        "London Map",
        "Newspapers",
        "Directory / Almanac",
        "Allies / Informants",
    ):
        assert resource in page.text
    assert page.text.count("Future") >= 4
    assert "Not available in this deterministic demo" in page.text
    assert 'id="human-message"' in page.text
    assert "Human participation coming later" in page.text
    assert 'id="human-message" rows="2" disabled' in page.text


def test_lead_visit_finalization_has_no_round_or_reasoning_precondition(
    task3_client,
) -> None:
    client, registry = task3_client
    prepare_finalizable(client, registry)
    before = registry.snapshot("session_001")
    assert before.rounds == before.analyses == before.decisions == ()

    page = client.get("/investigations/session_001")
    assert "Present Final Theory" in page.text
    response = client.post("/investigations/session_001/finalize")

    assert response.status_code == 303
    assert response.headers["location"] == "/investigations/session_001"
    completed = registry.snapshot("session_001")
    assert completed.status is InvestigationStatus.COMPLETED
    assert completed.final_theory is not None
    assert completed.rounds == completed.analyses == completed.decisions == ()
    detail = client.get(response.headers["location"])
    assert "Final Theory" in detail.text
    assert "apparent exit was staged" in detail.text
    assert "Supporting information" in detail.text
    assert "The window was open." in detail.text
    assert "The corridor was used." in detail.text


def test_completed_archive_keeps_history_and_rejects_all_mutations(
    task3_client,
) -> None:
    client, registry = task3_client
    visit_a = prepare_finalizable(client, registry)
    lead_a = registry.snapshot("session_001").leads[0]
    client.post(
        f"/investigations/session_001/visits/{visit_a.visit_id}/discussion"
    )
    client.post(
        "/investigations/session_001/leads",
        data={"reference": "95 NW"},
    )
    session = registry.snapshot("session_001")
    lead_b = session.leads[1]
    visit_b = session.visits[-1]
    assert client.post("/investigations/session_001/finalize").status_code == 303
    frozen = registry.snapshot("session_001")

    for lead in (lead_a, lead_b):
        page = client.get(f"/investigations/session_001?lead={lead.lead_id}")
        assert page.status_code == 200
        assert lead.label in page.text
        assert CASE_OPENING in page.text
        assert "Final Theory" in page.text
        assert "Read-only archive" in page.text
        assert "Visit new lead" not in page.text
        assert "Revisit lead" not in page.text
        assert "Add information" not in page.text
        assert "Continue discussion" not in page.text
        assert "Present Final Theory" not in page.text
        if lead.lead_id == lead_a.lead_id:
            assert "The globally disclosed facts" in page.text

    responses = (
        client.post("/investigations/session_001/finalize"),
        client.post(
            "/investigations/session_001/leads",
            data={"reference": "100 SW"},
        ),
        client.post(
            f"/investigations/session_001/leads/{lead_a.lead_id}/visit"
        ),
        client.post(
            f"/investigations/session_001/visits/{visit_b.visit_id}/information",
            data={"information": "Late information."},
        ),
        client.post(
            f"/investigations/session_001/visits/{visit_b.visit_id}/discussion"
        ),
    )
    assert all(response.status_code == 409 for response in responses)
    assert registry.snapshot("session_001") == frozen


def test_finalization_provider_failure_and_early_request_are_atomic(
    task3_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, registry = task3_client
    early = client.post("/investigations/session_001/finalize")
    assert early.status_code == 409
    prepare_finalizable(client, registry)
    before = registry.snapshot("session_001")

    def fail(*args, **kwargs):
        raise RuntimeError("provider failed")

    monkeypatch.setattr(routes, "finalize_lead_investigation", fail)
    response = client.post("/investigations/session_001/finalize")

    assert response.status_code == 500
    assert registry.snapshot("session_001") == before
    assert "previous investigation state was kept" in response.text.lower()
