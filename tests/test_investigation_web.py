"""Final Lead/Visit investigation HTTP contract tests."""

from pathlib import Path

import pytest

import multi_agent_personalities.web.investigation_routes as routes
from multi_agent_personalities.web.app import create_app
from multi_agent_personalities.web.investigation_store import (
    InMemoryInvestigationRegistry,
)
from tests.asgi_client import ASGITestClient


ROOT = Path(__file__).resolve().parents[1]
VALID_FORM = {
    "characters": ["sherlock", "poirot"],
    "case_id": "archive-absence",
}


@pytest.fixture
def web_client(tmp_path: Path):
    registry = InMemoryInvestigationRegistry()
    app = create_app(
        project_root=ROOT,
        output_root=tmp_path / "outputs",
        investigation_registry=registry,
    )
    with ASGITestClient(app) as client:
        yield client, registry, app


def test_router_exposes_only_lead_visit_mutations(web_client) -> None:
    _client, _registry, app = web_client
    investigation_routes = {
        (path, tuple(sorted(method.upper() for method in operations)))
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/investigations")
    }
    assert investigation_routes == {
        ("/investigations", ("GET", "POST")),
        ("/investigations/{session_id}", ("GET",)),
        ("/investigations/{session_id}/leads", ("POST",)),
        (
            "/investigations/{session_id}/leads/{lead_id}/visit",
            ("POST",),
        ),
        (
            "/investigations/{session_id}/visits/{visit_id}/information",
            ("POST",),
        ),
            (
                "/investigations/{session_id}/visits/{visit_id}/discussion",
                ("POST",),
            ),
            (
                "/investigations/{session_id}/visits/{visit_id}/interaction",
                ("POST",),
            ),
        ("/investigations/{session_id}/finalize", ("POST",)),
    }
    paths = {item[0] for item in investigation_routes}
    for suffix in ("clues", "analyses", "discussion", "decision"):
        assert f"/investigations/{{session_id}}/{suffix}" not in paths


def test_invalid_creation_preserves_submitted_values_and_registry(web_client) -> None:
    client, registry, _app = web_client
    response = client.post(
        "/investigations",
        data={"characters": ["sherlock"], "case_id": "archive-absence"},
    )

    assert response.status_code == 400
    assert registry.session_ids == ()
    assert 'value="archive-absence" checked' in response.text
    assert 'value="sherlock" checked' in response.text
    assert "Select all supported investigators" in response.text


def test_unknown_session_lead_and_visit_are_404_without_mutation(
    web_client,
) -> None:
    client, registry, _app = web_client
    unknown_session = client.get("/investigations/session_999")
    assert unknown_session.status_code == 404
    assert '>Conversations</a>' in unknown_session.text
    assert 'aria-current="page">Investigations</a>' in unknown_session.text
    client.post("/investigations", data=VALID_FORM)
    before = registry.snapshot("session_001")

    assert client.get("/investigations/session_001?lead=unknown").status_code == 404
    assert client.post(
        "/investigations/session_001/leads/session_001_lead_9999/visit"
    ).status_code == 404
    assert client.post(
        "/investigations/session_001/visits/session_001_visit_9999/information",
        data={"information": "Not retained."},
    ).status_code == 404
    assert client.post(
        "/investigations/session_001/visits/session_001_visit_9999/discussion"
    ).status_code == 404
    assert registry.snapshot("session_001") == before


def test_discussion_failure_is_500_and_atomic(
    web_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, registry, _app = web_client
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations/session_001/leads",
        data={"reference": "42 NW"},
    )
    visit = registry.snapshot("session_001").visits[-1]
    before = registry.snapshot("session_001")

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("provider failed")

    monkeypatch.setattr(routes, "continue_lead_discussion", fail)
    response = client.post(
        f"/investigations/session_001/visits/{visit.visit_id}/discussion"
    )

    assert response.status_code == 500
    assert registry.snapshot("session_001") == before
    assert "previous investigation state was kept" in response.text.lower()


def test_finalization_failure_is_500_active_and_atomic(
    web_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, registry, _app = web_client
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations/session_001/leads",
        data={"reference": "42 NW"},
    )
    visit = registry.snapshot("session_001").visits[-1]
    client.post(
        f"/investigations/session_001/visits/{visit.visit_id}/information",
        data={"information": "The inner door was used."},
    )
    before = registry.snapshot("session_001")

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("provider failed")

    monkeypatch.setattr(routes, "finalize_lead_investigation", fail)
    response = client.post("/investigations/session_001/finalize")

    assert response.status_code == 500
    assert registry.snapshot("session_001") == before
    assert registry.snapshot("session_001").final_theory is None
