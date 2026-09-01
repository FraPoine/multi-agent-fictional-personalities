"""Offline end-to-end HTTP coverage for the Lead/Visit investigation UX."""

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest

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


def create_session(client: ASGITestClient, introduction: str) -> str:
    response = client.post(
        "/investigations",
        data={"characters": CHARACTERS, "introduction": introduction},
    )
    assert response.status_code == 303
    return response.headers["location"].rsplit("/", 1)[-1]


def visit_lead(
    client: ASGITestClient,
    registry: InMemoryInvestigationRegistry,
    session_id: str,
    label: str,
) -> tuple[str, str]:
    references = {
        "Scotland Yard": "42 NW",
        "Baker Street": "95 NW",
        "Observatory": "42 NW",
        "Recital Room": "42 NW",
        "Dome Entrance": "95 NW",
        "Service Door": "95 NW",
    }
    response = client.post(
        f"/investigations/{session_id}/leads",
        data={"reference": references[label]},
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
    assert client.get("/investigations").status_code == 200
    session_id = create_session(
        client,
        "A visitor disappears after delivering a coded letter.",
    )
    opening = client.get(f"/investigations/{session_id}")
    assert opening.status_code == 200
    assert "Case opening" in opening.text

    lead_a, visit_a1 = visit_lead(client, registry, session_id, "Scotland Yard")
    reveal(client, session_id, visit_a1, "The window was open.")
    reveal(client, session_id, visit_a1, "The corridor was used.")
    discuss(client, session_id, visit_a1)
    a_first = client.get(f"/investigations/{session_id}?lead={lead_a}")
    assert "The globally disclosed facts" in a_first.text

    lead_b, visit_b = visit_lead(client, registry, session_id, "Baker Street")
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

    a_thread = client.get(f"/investigations/{session_id}?lead={lead_a}")
    b_thread = client.get(f"/investigations/{session_id}?lead={lead_b}")
    assert a_thread.text.count("The globally disclosed facts") == 2
    assert "Revisited · Visit 3" in a_thread.text
    assert b_thread.status_code == 200
    assert "A cipher key was left on the desk." in b_thread.text
    assert "Case Opening" in a_thread.text
    assert "How to investigate" in a_thread.text
    assert "London Map" in a_thread.text and "Future" in a_thread.text

    finalization = client.post(f"/investigations/{session_id}/finalize")
    assert finalization.status_code == 303
    completed = registry.snapshot(session_id)
    assert completed.status is InvestigationStatus.COMPLETED
    completed_page = client.get(finalization.headers["location"])
    assert "Final Theory" in completed_page.text
    assert "Read-only archive" in completed_page.text
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
    first = create_session(client, "The observatory ledger vanished.")
    second = create_session(client, "A violin disappeared from a sealed room.")
    assert (first, second) == ("session_001", "session_002")

    lead_a, visit_a = visit_lead(client, registry, first, "Observatory")
    lead_x, visit_x = visit_lead(client, registry, second, "Recital Room")
    reveal(client, first, visit_a, "The window was open.")
    reveal(client, second, visit_x, "The window was open.")
    reveal(client, first, visit_a, "The corridor was used.")
    reveal(client, second, visit_x, "The corridor was used.")
    discuss(client, second, visit_x)
    first_before = registry.snapshot(first)
    discuss(client, first, visit_a)
    assert registry.snapshot(second).conversation_runs[0].run_id.startswith(second)
    assert registry.snapshot(first).conversation_runs[0].run_id.startswith(first)

    lead_b, _visit_b = visit_lead(client, registry, first, "Dome Entrance")
    lead_y, _visit_y = visit_lead(client, registry, second, "Service Door")
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
