"""Final Lead/Visit investigation HTTP contract tests."""

from pathlib import Path

import pytest

import multi_agent_personalities.web.investigation_routes as routes
from multi_agent_personalities.web.app import create_app
from multi_agent_personalities.web.investigation_store import (
    InMemoryInvestigationRegistry,
)
from multi_agent_personalities.case_catalog import default_case_catalog_directory
from multi_agent_personalities.web.investigation_presentation import present_session
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
        include_compatibility_cases=True,
    )
    with ASGITestClient(app) as client:
        yield client, registry, app


def test_router_exposes_investigation_mutations(web_client) -> None:
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
            "/investigations/{session_id}/leads/{lead_id}/rename",
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
        ("/investigations/{session_id}/resources/{resource_id}/consult", ("POST",)),
        ("/investigations/{session_id}/conclusion/start", ("POST",)),
        ("/investigations/{session_id}/conclusion/drafts", ("POST",)),
        ("/investigations/{session_id}/conclusion/answers/{question_id}", ("POST",)),
        ("/investigations/{session_id}/conclusion/lock", ("POST",)),
        ("/investigations/{session_id}/conclusion/answer-elements", ("POST",)),
        ("/investigations/{session_id}/conclusion/score", ("POST",)),
        ("/investigations/{session_id}/conclusion/solution", ("POST",)),
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


def test_default_app_rejects_forged_compatibility_case_without_creation(
    tmp_path: Path,
) -> None:
    app = create_app(project_root=ROOT, output_root=tmp_path / "outputs")
    registry = app.state.investigation_registry
    before = registry.session_ids
    with ASGITestClient(app) as client:
        response = client.post(
            "/investigations",
            data={
                "characters": ["sherlock", "poirot"],
                "case_id": "archive-absence",
            },
        )
    assert response.status_code == 404
    assert registry.session_ids == before


def test_explicit_compatibility_mode_keeps_synthetic_creation(web_client) -> None:
    client, registry, _app = web_client
    response = client.post("/investigations", data=VALID_FORM)
    assert response.status_code == 303
    assert registry.snapshot("session_001").case_id == "archive-absence"


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


def test_runtime_lead_rename_http_contract_and_archive_presentation(
    web_client,
) -> None:
    client, registry, _app = web_client
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations/session_001/leads",
        data={"reference": "42 NW"},
    )
    lead = registry.snapshot("session_001").leads[0]
    presentation_args = {
        "case_catalog": registry.case_catalog,
        "resource_base_directory": default_case_catalog_directory(ROOT).parent,
    }
    initial = present_session(registry.get("session_001"), **presentation_args)
    assert initial.leads[0].label == initial.leads[0].original_label == lead.label
    assert initial.leads[0].custom_label is None

    renamed_response = client.post(
        f"/investigations/session_001/leads/{lead.lead_id}/rename",
        data={"custom_label": "  House of Lestrade  "},
    )
    assert renamed_response.status_code == 303
    assert renamed_response.headers["location"].endswith(f"?lead={lead.lead_id}")
    renamed = registry.snapshot("session_001")
    assert renamed.leads[0].label == lead.label
    assert renamed.leads[0].custom_label == "House of Lestrade"
    presented = present_session(
        registry.get("session_001"),
        selected_lead_id=lead.lead_id,
        **presentation_args,
    )
    assert presented.leads[0].label == "House of Lestrade"
    assert presented.leads[0].original_label == lead.label
    assert presented.leads[0].reference == lead.reference
    assert presented.selected_lead.label == "House of Lestrade"
    assert presented.selected_lead.original_label == lead.label
    assert presented.selected_lead.custom_label == "House of Lestrade"
    assert presented.selected_lead.reference == lead.reference

    before_failure = registry.snapshot("session_001").model_dump_json()
    assert client.post(
        f"/investigations/session_999/leads/{lead.lead_id}/rename",
        data={"custom_label": "Unknown session"},
    ).status_code == 404
    assert client.post(
        "/investigations/session_001/leads/missing/rename",
        data={"custom_label": "Unknown"},
    ).status_code == 404
    assert client.post(
        f"/investigations/session_001/leads/{lead.lead_id}/rename",
        data={"custom_label": "   "},
    ).status_code == 400
    assert client.post(
        f"/investigations/session_001/leads/{lead.lead_id}/rename",
        data={"custom_label": "x" * 121},
    ).status_code == 400
    assert registry.snapshot("session_001").model_dump_json() == before_failure

    visit = registry.snapshot("session_001").visits[-1]
    for information in ("The window was open.", "The corridor was used."):
        assert client.post(
            f"/investigations/session_001/visits/{visit.visit_id}/information",
            data={"information": information},
        ).status_code == 303
    assert client.post("/investigations/session_001/finalize").status_code == 303
    completed_before = registry.snapshot("session_001").model_dump_json()
    assert client.post(
        f"/investigations/session_001/leads/{lead.lead_id}/rename",
        data={"custom_label": "Blocked"},
    ).status_code == 409
    assert registry.snapshot("session_001").model_dump_json() == completed_before
    archive = client.get(
        f"/investigations/session_001?lead={lead.lead_id}"
    )
    assert archive.status_code == 200
    assert "House of Lestrade" in archive.text

    assert client.post(
        "/investigations",
        data={
            "characters": ["sherlock", "poirot"],
            "case_id": "demo-1-vanishing-from-hyde-park",
        },
    ).status_code == 303
    assert client.post(
        "/investigations/session_002/leads", data={"reference": "17 WC"}
    ).status_code == 303
    conclusion_lead = registry.snapshot("session_002").leads[0]
    assert client.post(
        "/investigations/session_002/conclusion/start"
    ).status_code == 303
    conclusion_before = registry.snapshot("session_002").model_dump_json()
    assert client.post(
        f"/investigations/session_002/leads/{conclusion_lead.lead_id}/rename",
        data={"custom_label": "Blocked"},
    ).status_code == 409
    assert registry.snapshot("session_002").model_dump_json() == conclusion_before


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
