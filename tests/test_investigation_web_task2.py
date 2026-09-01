"""Sprint 7 Lead/Visit UX redesign Task 2 route checks."""

from pathlib import Path

import pytest

import multi_agent_personalities.web.investigation_routes as routes
import multi_agent_personalities.web.investigation_presentation as presentation
from multi_agent_personalities.web.app import create_app
from multi_agent_personalities.web.investigation_store import InMemoryInvestigationRegistry
from tests.asgi_client import ASGITestClient


ROOT = Path(__file__).resolve().parents[1]
CREATE_FORM = {
    "characters": ["sherlock", "poirot"],
    "case_id": "archive-absence",
}


@pytest.fixture
def task2_client(tmp_path: Path):
    registry = InMemoryInvestigationRegistry()
    app = create_app(
        project_root=ROOT,
        output_root=tmp_path / "outputs",
        investigation_registry=registry,
    )
    with ASGITestClient(app) as client:
        assert client.post("/investigations", data=CREATE_FORM).status_code == 303
        yield client, registry


def visit_new(client: ASGITestClient, label: str, kind: str = "place"):
    references = {"Scotland Yard": "42 NW", "Baker Street": "95 NW"}
    return client.post(
        "/investigations/session_001/leads",
        data={"reference": references[label]},
    )


def test_get_selection_is_read_only_and_unknown_lead_is_404(task2_client) -> None:
    client, registry = task2_client
    visit_new(client, "Scotland Yard")
    visit_new(client, "Baker Street")
    session = registry.snapshot("session_001")
    lead_a = session.leads[0]
    frozen = session.model_dump_json()

    selected = client.get(f"/investigations/session_001?lead={lead_a.lead_id}")

    assert selected.status_code == 200
    assert registry.snapshot("session_001").model_dump_json() == frozen
    assert "Archive Room" in selected.text
    assert "Historical lead" in selected.text
    assert "Revisit lead" in selected.text
    assert "Continue discussion" not in selected.text
    assert client.get("/investigations/session_001?lead=unknown").status_code == 404


def test_invalid_forms_and_unknown_scoped_resources_use_400_or_404(
    task2_client,
) -> None:
    client, registry = task2_client

    invalid_lead = client.post(
        "/investigations/session_001/leads",
        data={"reference": " "},
    )
    assert invalid_lead.status_code == 400
    assert registry.snapshot("session_001").visits == ()

    malformed_reference = client.post(
        "/investigations/session_001/leads",
        data={"reference": "not a physical reference"},
    )
    unknown_reference = client.post(
        "/investigations/session_001/leads",
        data={"reference": "100 SW"},
    )
    other_scheme_reference = client.post(
        "/investigations/session_001/leads",
        data={"reference": "GF-26"},
    )
    assert malformed_reference.status_code == 400
    assert unknown_reference.status_code == 404
    assert other_scheme_reference.status_code == 404
    assert registry.snapshot("session_001").visits == ()

    unknown_lead = client.post(
        "/investigations/session_001/leads/session_001_lead_9999/visit"
    )
    unknown_information = client.post(
        "/investigations/session_001/visits/session_001_visit_9999/information",
        data={"information": "Not stored."},
    )
    unknown_discussion = client.post(
        "/investigations/session_001/visits/session_001_visit_9999/discussion"
    )
    assert unknown_lead.status_code == 404
    assert unknown_information.status_code == 404
    assert unknown_discussion.status_code == 404
    assert registry.snapshot("session_001").visits == ()


def test_reference_entry_never_revisits_implicitly(task2_client) -> None:
    client, registry = task2_client
    assert visit_new(client, "Scotland Yard").status_code == 303
    lead_a = registry.snapshot("session_001").leads[0]

    current = visit_new(client, "Scotland Yard")
    assert current.status_code == 409
    assert len(registry.snapshot("session_001").visits) == 1

    assert visit_new(client, "Baker Street").status_code == 303
    before = registry.snapshot("session_001")
    historical = visit_new(client, "Scotland Yard")

    assert historical.status_code == 303
    assert historical.headers["location"].endswith(f"?lead={lead_a.lead_id}")
    assert registry.snapshot("session_001") == before
    assert len(before.visits) == 2


def test_new_lead_and_explicit_revisit_preserve_semantic_identity(task2_client) -> None:
    client, registry = task2_client
    assert visit_new(client, "Scotland Yard").status_code == 303
    first = registry.snapshot("session_001")
    lead_a = first.leads[0]
    assert first.visits[0].lead_id == lead_a.lead_id

    assert visit_new(client, "Baker Street").status_code == 303
    before_selection = registry.snapshot("session_001")
    client.get(f"/investigations/session_001?lead={lead_a.lead_id}")
    assert len(registry.snapshot("session_001").visits) == 2

    response = client.post(
        f"/investigations/session_001/leads/{lead_a.lead_id}/visit"
    )

    assert response.status_code == 303
    session = registry.snapshot("session_001")
    assert session.leads == before_selection.leads
    assert len(session.leads) == 2
    assert len(session.visits) == 3
    assert session.visits[0].lead_id == session.visits[2].lead_id == lead_a.lead_id
    page = client.get(response.headers["location"])
    assert page.text.count(">Archive Room<") == 2  # sidebar and thread heading
    assert page.text.count("42 NW") >= 2  # prominent in sidebar and thread header
    assert "2 visits" in page.text
    assert "Revisited · Visit 3" in page.text


def test_information_is_global_and_historical_write_is_atomic(task2_client) -> None:
    client, registry = task2_client
    visit_new(client, "Scotland Yard")
    visit_a = registry.snapshot("session_001").visits[-1]
    first = client.post(
        f"/investigations/session_001/visits/{visit_a.visit_id}/information",
        data={"information": "A constable retained the envelope."},
    )
    assert first.status_code == 303

    visit_new(client, "Baker Street")
    visit_b = registry.snapshot("session_001").visits[-1]
    second = client.post(
        f"/investigations/session_001/visits/{visit_b.visit_id}/information",
        data={"information": "The paper bears a London watermark."},
    )
    assert second.status_code == 303
    before = registry.snapshot("session_001")

    stale = client.post(
        f"/investigations/session_001/visits/{visit_a.visit_id}/information",
        data={"information": "This must not be stored."},
    )

    assert stale.status_code == 409
    after = registry.snapshot("session_001")
    assert after == before
    assert [item.text for item in after.revealed_information] == [
        "A constable retained the envelope.",
        "The paper bears a London watermark.",
    ]
    assert "historical visit is read-only" in stale.text


def test_a_b_a_discussion_projects_one_persistent_lead_thread(task2_client) -> None:
    client, registry = task2_client
    visit_new(client, "Scotland Yard")
    session = registry.snapshot("session_001")
    lead_a = session.leads[0]
    visit_a1 = session.visits[-1]

    first = client.post(
        f"/investigations/session_001/visits/{visit_a1.visit_id}/discussion"
    )
    repeat = client.post(
        f"/investigations/session_001/visits/{visit_a1.visit_id}/discussion"
    )
    assert first.status_code == repeat.status_code == 303

    visit_new(client, "Baker Street")
    session = registry.snapshot("session_001")
    lead_b = session.leads[1]
    visit_b = session.visits[-1]
    assert client.post(
        f"/investigations/session_001/visits/{visit_b.visit_id}/discussion"
    ).status_code == 303

    stale = client.post(
        f"/investigations/session_001/visits/{visit_a1.visit_id}/discussion"
    )
    assert stale.status_code == 409

    assert client.post(
        f"/investigations/session_001/leads/{lead_a.lead_id}/visit"
    ).status_code == 303
    visit_a2 = registry.snapshot("session_001").visits[-1]
    assert client.post(
        f"/investigations/session_001/visits/{visit_a2.visit_id}/discussion"
    ).status_code == 303

    session = registry.snapshot("session_001")
    assert len(session.conversation_runs) == 4
    assert len(session.visits[0].conversation_run_ids) == 2
    assert len(session.visits[2].conversation_run_ids) == 1
    a_page = client.get(f"/investigations/session_001?lead={lead_a.lead_id}")
    b_page = client.get(f"/investigations/session_001?lead={lead_b.lead_id}")
    assert a_page.status_code == b_page.status_code == 200
    assert a_page.text.count("The globally disclosed facts") == 3
    assert a_page.text.count("The chronology is useful") == 3
    assert "6 discussion messages across 2 visits" in a_page.text
    assert b_page.text.count("The globally disclosed facts") == 1
    assert "Historical lead" in b_page.text


def test_visit_groups_follow_authoritative_projected_message_order(
    task2_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, registry = task2_client
    visit_new(client, "Scotland Yard")
    session = registry.snapshot("session_001")
    lead_a = session.leads[0]
    visit_a1 = session.visits[-1]
    assert client.post(
        f"/investigations/session_001/visits/{visit_a1.visit_id}/discussion"
    ).status_code == 303

    visit_new(client, "Baker Street")
    session = registry.snapshot("session_001")
    lead_b = session.leads[1]
    visit_b = session.visits[-1]
    assert client.post(
        f"/investigations/session_001/visits/{visit_b.visit_id}/discussion"
    ).status_code == 303
    assert client.post(
        f"/investigations/session_001/leads/{lead_a.lead_id}/visit"
    ).status_code == 303
    visit_a2 = registry.snapshot("session_001").visits[-1]
    assert client.post(
        f"/investigations/session_001/visits/{visit_a2.visit_id}/discussion"
    ).status_code == 303

    session = registry.snapshot("session_001")
    visit_by_id = {visit.visit_id: visit for visit in session.visits}
    visit_a1 = visit_by_id[visit_a1.visit_id]
    visit_b = visit_by_id[visit_b.visit_id]
    visit_a2 = visit_by_id[visit_a2.visit_id]
    authoritative = presentation.project_lead_conversation
    projected_a = authoritative(session, lead_a.lead_id)
    projected_b = authoritative(session, lead_b.lead_id)
    assert [message.run_id for message in projected_a] == [
        visit_a1.conversation_run_ids[0],
        visit_a1.conversation_run_ids[0],
        visit_a2.conversation_run_ids[0],
        visit_a2.conversation_run_ids[0],
    ]
    assert [message.run_id for message in projected_b] == [
        visit_b.conversation_run_ids[0],
        visit_b.conversation_run_ids[0],
    ]

    # Reverse each run's authoritative message order. A presenter that walks
    # ConversationRun.messages independently will fail these assertions.
    def reverse_messages_within_runs(session, lead_id):
        projected = authoritative(session, lead_id)
        return tuple(
            message
            for run_id in dict.fromkeys(item.run_id for item in projected)
            for message in reversed(
                tuple(item for item in projected if item.run_id == run_id)
            )
        )

    monkeypatch.setattr(
        presentation,
        "project_lead_conversation",
        reverse_messages_within_runs,
    )
    a_page = client.get(f"/investigations/session_001?lead={lead_a.lead_id}")
    b_page = client.get(f"/investigations/session_001?lead={lead_b.lead_id}")

    assert a_page.status_code == b_page.status_code == 200
    assert a_page.text.index("The chronology is useful") < a_page.text.index(
        "The globally disclosed facts"
    )
    assert a_page.text.index("First visit") < a_page.text.index(
        "Revisited · Visit 3"
    )
    assert b_page.text.index("The chronology is useful") < b_page.text.index(
        "The globally disclosed facts"
    )


def test_discussion_provider_failure_is_500_and_atomic(
    task2_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, registry = task2_client
    visit_new(client, "Scotland Yard")
    visit = registry.snapshot("session_001").visits[-1]
    before = registry.snapshot("session_001")

    def fail(*args, **kwargs):
        raise RuntimeError("provider failed")

    monkeypatch.setattr(routes, "continue_lead_discussion", fail)
    response = client.post(
        f"/investigations/session_001/visits/{visit.visit_id}/discussion"
    )

    assert response.status_code == 500
    assert registry.snapshot("session_001") == before
    assert "previous investigation state was kept" in response.text.lower()
