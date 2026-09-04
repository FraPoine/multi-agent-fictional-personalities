"""Offline end-to-end HTTP coverage for the Lead/Visit investigation UX."""

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest

from multi_agent_personalities.case_catalog import (
    CaseCatalog,
    CaseDefinition,
    CaseLeadDefinition,
    CaseResourceDefinition,
)
from multi_agent_personalities.models import InvestigationStatus
from multi_agent_personalities.web.app import create_app
from multi_agent_personalities.web.investigation_store import (
    InMemoryInvestigationRegistry,
)
from tests.asgi_client import ASGITestClient


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ["sherlock", "poirot"]


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)


@pytest.fixture
def http_workflow(
    tmp_path: Path,
) -> Iterator[tuple[ASGITestClient, InMemoryInvestigationRegistry, Path]]:
    registry = InMemoryInvestigationRegistry()
    output_root = tmp_path / "outputs"
    app = create_app(
        project_root=ROOT,
        output_root=output_root,
        investigation_registry=registry,
    )
    with ASGITestClient(app) as client:
        yield client, registry, output_root


def create_session(client: ASGITestClient, case_id: str = "archive-absence") -> str:
    response = client.post(
        "/investigations",
        data={"characters": CHARACTERS, "case_id": case_id},
    )
    assert response.status_code == 303
    return response.headers["location"].rsplit("/", 1)[-1]


def visit_lead(
    client: ASGITestClient,
    registry: InMemoryInvestigationRegistry,
    session_id: str,
    reference: str,
) -> tuple[str, str]:
    response = client.post(
        f"/investigations/{session_id}/leads",
        data={"reference": reference},
    )
    assert response.status_code == 303
    session = registry.snapshot(session_id)
    return session.leads[-1].lead_id, session.visits[-1].visit_id


def reveal(
    client: ASGITestClient,
    session_id: str,
    visit_id: str,
    text: str,
) -> None:
    response = client.post(
        f"/investigations/{session_id}/visits/{visit_id}/information",
        data={"information": text},
    )
    assert response.status_code == 303


def discuss(client: ASGITestClient, session_id: str, visit_id: str) -> None:
    response = client.post(
        f"/investigations/{session_id}/visits/{visit_id}/discussion"
    )
    assert response.status_code == 303


def test_complete_a_b_a_workflow_through_real_http(http_workflow) -> None:
    client, registry, output_root = http_workflow
    lobby = client.get("/investigations")
    assert lobby.status_code == 200
    assert "The Archive Absence" in lobby.text
    assert "The Observatory Signal" in lobby.text
    session_id = create_session(client)
    opening = client.get(f"/investigations/{session_id}")
    assert opening.status_code == 200
    assert "The Archive Absence" in opening.text
    assert "A researcher is missing from a locked archive room." in opening.text

    lead_a, visit_a1 = visit_lead(client, registry, session_id, "42 NW")
    first_snapshot = registry.snapshot(session_id)
    assert len(first_snapshot.leads) == len(first_snapshot.visits) == 1
    assert first_snapshot.leads[0].case_lead_key == "archive-room"
    assert first_snapshot.leads[0].reference == "42 NW"
    reveal(client, session_id, visit_a1, "The window was open.")
    reveal(client, session_id, visit_a1, "The corridor was used.")
    discuss(client, session_id, visit_a1)
    a_first = client.get(f"/investigations/{session_id}?lead={lead_a}")
    assert "The globally disclosed facts" in a_first.text

    lead_b, visit_b = visit_lead(client, registry, session_id, "95 NW")
    reveal(client, session_id, visit_b, "A cipher key was left on the desk.")
    discuss(client, session_id, visit_b)
    before_selection = registry.snapshot(session_id)
    historical_a = client.get(f"/investigations/{session_id}?lead={lead_a}")
    assert historical_a.status_code == 200
    assert "Historical lead" in historical_a.text
    assert registry.snapshot(session_id) == before_selection

    stale_info = client.post(
        f"/investigations/{session_id}/visits/{visit_a1}/information",
        data={"information": "Must not be retained."},
    )
    stale_discussion = client.post(
        f"/investigations/{session_id}/visits/{visit_a1}/discussion"
    )
    assert stale_info.status_code == stale_discussion.status_code == 409
    assert registry.snapshot(session_id) == before_selection

    revisit = client.post(
        f"/investigations/{session_id}/leads/{lead_a}/visit"
    )
    assert revisit.status_code == 303
    visit_a2 = registry.snapshot(session_id).visits[-1]
    assert visit_a2.lead_id == lead_a
    assert visit_a2.visit_index == 3
    discuss(client, session_id, visit_a2.visit_id)
    revisited_snapshot = registry.snapshot(session_id)
    assert revisited_snapshot.leads[0].reference == "42 NW"
    assert len(revisited_snapshot.visits[0].conversation_run_ids) == 1
    assert len(revisited_snapshot.visits[2].conversation_run_ids) == 1

    a_thread = client.get(f"/investigations/{session_id}?lead={lead_a}")
    b_thread = client.get(f"/investigations/{session_id}?lead={lead_b}")
    assert a_thread.text.count("The globally disclosed facts") == 2
    assert "Revisited · Visit 3" in a_thread.text
    assert b_thread.status_code == 200
    assert "A cipher key was left on the desk." in b_thread.text
    assert "Case Opening" in a_thread.text
    assert "How to investigate" in a_thread.text
    assert "Synthetic London Overview" in a_thread.text
    assert 'data-map-select="london-overview"' in a_thread.text
    assert 'data-map-select="archive-district"' in a_thread.text
    assert "Archive Gazette" in a_thread.text
    assert "London Directory" in a_thread.text
    assert "Observatory Journal" not in a_thread.text
    assert "Local asset unavailable." in a_thread.text

    finalization = client.post(f"/investigations/{session_id}/finalize")
    assert finalization.status_code == 303
    completed = registry.snapshot(session_id)
    assert completed.status is InvestigationStatus.COMPLETED
    completed_page = client.get(finalization.headers["location"])
    assert "Final Theory" in completed_page.text
    assert "Read-only archive" in completed_page.text
    assert "Synthetic London Overview" in completed_page.text
    assert "The globally disclosed facts" in completed_page.text
    assert "Visit new lead" not in completed_page.text
    assert "Continue discussion" not in completed_page.text
    frozen = registry.snapshot(session_id)
    assert client.post(
        f"/investigations/{session_id}/visits/{visit_a2.visit_id}/discussion"
    ).status_code == 409
    assert registry.snapshot(session_id) == frozen
    assert not output_root.exists()


def test_interleaved_sessions_are_isolated(http_workflow) -> None:
    client, registry, output_root = http_workflow
    first = create_session(client, "archive-absence")
    second = create_session(client, "observatory-signal")
    assert (first, second) == ("session_001", "session_002")
    first_page = client.get(f"/investigations/{first}")
    second_page = client.get(f"/investigations/{second}")
    assert "The Archive Absence" in first_page.text
    assert "Synthetic London Overview" in first_page.text
    assert "Observatory Floor Plan" not in first_page.text
    assert "The Observatory Signal" in second_page.text
    assert "Observatory Floor Plan" in second_page.text
    assert "Archive Gazette" not in second_page.text

    lead_a, visit_a = visit_lead(client, registry, first, "42 NW")
    lead_x, visit_x = visit_lead(client, registry, second, "GF-26")
    reveal(client, first, visit_a, "The window was open.")
    reveal(client, second, visit_x, "The window was open.")
    reveal(client, first, visit_a, "The corridor was used.")
    reveal(client, second, visit_x, "The corridor was used.")
    discuss(client, second, visit_x)
    first_before = registry.snapshot(first)
    discuss(client, first, visit_a)
    assert registry.snapshot(second).conversation_runs[0].run_id.startswith(second)
    assert registry.snapshot(first).conversation_runs[0].run_id.startswith(first)

    lead_b, _visit_b = visit_lead(client, registry, first, "95 NW")
    lead_y, _visit_y = visit_lead(client, registry, second, "FF-1")
    first_selected = registry.snapshot(first)
    second_selected = registry.snapshot(second)
    assert client.get(f"/investigations/{first}?lead={lead_a}").status_code == 200
    assert client.get(f"/investigations/{second}?lead={lead_x}").status_code == 200
    assert registry.snapshot(first) == first_selected
    assert registry.snapshot(second) == second_selected

    assert client.post(
        f"/investigations/{first}/leads/{lead_a}/visit"
    ).status_code == 303
    assert len(registry.snapshot(first).visits) == 3
    assert len(registry.snapshot(second).visits) == 2
    assert lead_b not in {item.lead_id for item in registry.snapshot(second).leads}
    assert lead_y not in {item.lead_id for item in registry.snapshot(first).leads}
    assert registry.snapshot(first) != first_before

    assert client.post(f"/investigations/{second}/finalize").status_code == 303
    assert registry.snapshot(second).status is InvestigationStatus.COMPLETED
    assert registry.snapshot(first).status is InvestigationStatus.ACTIVE
    assert registry.snapshot(first).final_theory is None
    assert not output_root.exists()


def test_same_reference_resolves_per_case_through_http(tmp_path: Path) -> None:
    catalogue = CaseCatalog(
        cases=(
            CaseDefinition(
                case_id="case-a",
                title="Synthetic Case A",
                short_description="First injected offline case.",
                opening="Case A has a sealed archive.",
                leads=(
                    CaseLeadDefinition(
                        lead_key="case-a-archive",
                        reference="42 NW",
                        reference_scheme="london-address",
                        label="Case A Archive",
                        kind="place",
                    ),
                ),
                resource_refs=("case-a-map", "case-a-paper"),
            ),
            CaseDefinition(
                case_id="case-b",
                title="Synthetic Case B",
                short_description="Second injected offline case.",
                opening="Case B has an unattended station.",
                leads=(
                    CaseLeadDefinition(
                        lead_key="case-b-station",
                        reference="42 NW",
                        reference_scheme="london-address",
                        label="Case B Station",
                        kind="place",
                    ),
                ),
                resource_refs=("case-b-map", "case-b-paper"),
            ),
        ),
        resources=(
            CaseResourceDefinition(
                resource_id="case-a-map",
                type="map",
                title="Case A Map",
            ),
            CaseResourceDefinition(
                resource_id="case-a-paper",
                type="newspaper",
                title="Case A Paper",
            ),
            CaseResourceDefinition(
                resource_id="case-b-map",
                type="map",
                title="Case B Map",
            ),
            CaseResourceDefinition(
                resource_id="case-b-paper",
                type="newspaper",
                title="Case B Paper",
            ),
        ),
    )
    registry = InMemoryInvestigationRegistry(case_catalog=catalogue)
    app = create_app(
        project_root=ROOT,
        output_root=tmp_path / "outputs",
        investigation_registry=registry,
        case_catalog=catalogue,
    )

    with ASGITestClient(app) as client:
        lobby = client.get("/investigations")
        assert lobby.status_code == 200
        assert "Synthetic Case A" in lobby.text
        assert "Synthetic Case B" in lobby.text
        first = create_session(client, "case-a")
        second = create_session(client, "case-b")

        lead_a, visit_a = visit_lead(client, registry, first, "42 NW")
        lead_b, visit_b = visit_lead(client, registry, second, "NW42")
        snapshot_a = registry.snapshot(first)
        snapshot_b = registry.snapshot(second)
        runtime_a = snapshot_a.leads[0]
        runtime_b = snapshot_b.leads[0]
        assert snapshot_a.case_id == "case-a"
        assert snapshot_b.case_id == "case-b"
        assert snapshot_a.case_introduction == "Case A has a sealed archive."
        assert snapshot_b.case_introduction == "Case B has an unattended station."
        assert runtime_a.reference == runtime_b.reference == "42 NW"
        assert (runtime_a.case_lead_key, runtime_a.label) == (
            "case-a-archive",
            "Case A Archive",
        )
        assert (runtime_b.case_lead_key, runtime_b.label) == (
            "case-b-station",
            "Case B Station",
        )

        reveal(client, first, visit_a, "Only Case A knows the archive window.")
        reveal(client, second, visit_b, "Only Case B knows the station clock.")
        discuss(client, first, visit_a)
        discuss(client, second, visit_b)
        snapshot_a = registry.snapshot(first)
        snapshot_b = registry.snapshot(second)
        assert snapshot_a.conversation_runs[0].run_id.startswith(first)
        assert snapshot_b.conversation_runs[0].run_id.startswith(second)
        assert lead_a not in {lead.lead_id for lead in snapshot_b.leads}
        assert lead_b not in {lead.lead_id for lead in snapshot_a.leads}

        page_a = client.get(f"/investigations/{first}?lead={lead_a}")
        page_b = client.get(f"/investigations/{second}?lead={lead_b}")
        assert "Only Case A knows the archive window." in page_a.text
        assert "Only Case B knows the station clock." not in page_a.text
        assert "Case A Map" in page_a.text and "Case B Map" not in page_a.text
        assert "Case A Paper" in page_a.text and "Case B Paper" not in page_a.text
        assert "Only Case B knows the station clock." in page_b.text
        assert "Only Case A knows the archive window." not in page_b.text
        assert "Case B Map" in page_b.text and "Case A Map" not in page_b.text
        assert "Case B Paper" in page_b.text and "Case A Paper" not in page_b.text
