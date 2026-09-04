"""Task 4 browser integration for authored resources and conclusions."""

from pathlib import Path

import pytest

from multi_agent_personalities.web.app import create_app
from multi_agent_personalities.web import investigation_routes
from tests.asgi_client import ASGITestClient


ROOT = Path(__file__).resolve().parents[1]
TEAM = ["sherlock", "poirot"]
DEMO1 = "demo-1-vanishing-from-hyde-park"


@pytest.fixture
def authored_web(tmp_path: Path):
    app = create_app(project_root=ROOT, output_root=tmp_path / "outputs")
    with ASGITestClient(app) as client:
        yield client, app.state.investigation_registry


def create_demo(client: ASGITestClient, case_id: str = DEMO1) -> str:
    response = client.post("/investigations", data={"characters": TEAM, "case_id": case_id})
    assert response.status_code == 303
    return response.headers["location"].rsplit("/", 1)[-1]


def test_normal_lobby_lists_authored_cases_not_compatibility_fixtures(authored_web) -> None:
    client, _registry = authored_web
    page = client.get("/investigations")
    assert page.status_code == 200
    assert "Vanishing from Hyde Park" in page.text
    assert "An Irregular Meeting" in page.text
    assert "The Disappearance of a Student" in page.text
    assert "The Archive Absence" not in page.text
    assert "The Observatory Signal" not in page.text


def test_resource_get_and_consultation_http_contract(authored_web) -> None:
    client, registry = authored_web
    session_id = create_demo(client)
    page = client.get(f"/investigations/{session_id}")
    assert '<aside class="resource-rail" aria-label="Investigation resources">' in page.text
    assert "case-resource-gallery" not in page.text
    assert "conclusion-panel--start" in page.text
    assert "Answer final questions" in page.text
    before = registry.snapshot(session_id).model_dump_json()
    image = client.get(f"/case-assets/assets/{DEMO1}/directory.png")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert registry.snapshot(session_id).model_dump_json() == before
    resource_id = f"{DEMO1}-directory"
    consulted = client.post(f"/investigations/{session_id}/resources/{resource_id}/consult")
    assert consulted.status_code == 303
    assert tuple(item.resource_id for item in registry.snapshot(session_id).resource_consultations) == (resource_id,)
    repeated = client.post(f"/investigations/{session_id}/resources/{resource_id}/consult")
    assert repeated.status_code == 303
    assert len(registry.snapshot(session_id).resource_consultations) == 1
    snapshot = registry.snapshot(session_id).model_dump_json()
    blocked = client.post(f"/investigations/{session_id}/resources/{DEMO1}-map/consult")
    assert blocked.status_code == 409 and registry.snapshot(session_id).model_dump_json() == snapshot
    unknown = client.post(f"/investigations/{session_id}/resources/unknown/consult")
    assert unknown.status_code == 404 and registry.snapshot(session_id).model_dump_json() == snapshot


def test_consulted_resources_reach_discussion_context_and_sessions_are_isolated(
    authored_web, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, registry = authored_web
    first = create_demo(client)
    second = create_demo(client)
    directory_id = f"{DEMO1}-directory"
    newspaper_id = f"{DEMO1}-newspaper"
    assert client.post(f"/investigations/{first}/resources/{directory_id}/consult").status_code == 303
    assert registry.snapshot(second).resource_consultations == ()
    directory_text = registry.resource_text_catalog.get(DEMO1, directory_id).entries[0].texts["en"]
    newspaper_text = registry.resource_text_catalog.get(DEMO1, newspaper_id).entries[0].texts["en"]
    captured: list[str] = []
    original = investigation_routes.continue_lead_discussion

    def recording_discussion(*args, **kwargs):
        result = original(*args, **kwargs)
        captured.append(result.context)
        return result

    monkeypatch.setattr(investigation_routes, "continue_lead_discussion", recording_discussion)
    assert client.post(f"/investigations/{first}/leads", data={"reference": "17 WC"}).status_code == 303
    visit_id = registry.snapshot(first).visits[-1].visit_id
    assert client.post(f"/investigations/{first}/visits/{visit_id}/discussion").status_code == 303
    assert directory_text in captured[-1]
    assert newspaper_text not in captured[-1]


def test_demo1_web_conclusion_preserves_reviewed_140_100_and_archive(authored_web) -> None:
    client, registry = authored_web
    session_id = create_demo(client)
    lead = client.post(f"/investigations/{session_id}/leads", data={"reference": "17 WC"})
    assert lead.status_code == 303
    visit_id = registry.snapshot(session_id).visits[-1].visit_id
    assert client.post(f"/investigations/{session_id}/visits/{visit_id}/information", data={"information": "forbidden"}).status_code == 409
    assert client.post(f"/investigations/{session_id}/conclusion/start").status_code == 303
    assert client.post(f"/investigations/{session_id}/conclusion/drafts").status_code == 303
    assert client.post(f"/investigations/{session_id}/conclusion/answers/q1", data={"answer": "Edited investigator answer"}).status_code == 303
    assert client.post(f"/investigations/{session_id}/conclusion/lock").status_code == 303
    assert client.post(f"/investigations/{session_id}/conclusion/answer-elements").status_code == 303
    elements = [item.element_id for item in registry.snapshot(session_id).conclusion.answer_elements]
    assert client.post(f"/investigations/{session_id}/conclusion/score", data={"awarded_element": elements}).status_code == 303
    score = registry.snapshot(session_id).conclusion.score_result
    assert (score.answer_element_total, score.printed_holmes_score, score.needs_review) == (140, 100, True)
    page = client.get(f"/investigations/{session_id}")
    assert "total 140 while the source says Holmes scored 100" in page.text
    assert client.post(f"/investigations/{session_id}/conclusion/solution").status_code == 303
    completed = registry.snapshot(session_id)
    assert completed.status.value == "completed"
    before = completed.model_dump_json()
    assert client.post(f"/investigations/{session_id}/conclusion/solution").status_code == 409
    assert client.post(f"/investigations/{session_id}/resources/{DEMO1}-directory/consult").status_code == 409
    assert registry.snapshot(session_id).model_dump_json() == before
    assert "Official solution" in client.get(f"/investigations/{session_id}").text


def test_demo2_gates_break_in_closure_and_score_band_through_http(authored_web) -> None:
    client, registry = authored_web
    case_id = "demo-2-an-irregular-meeting"
    session_id = create_demo(client, case_id)
    assert client.post(f"/investigations/{session_id}/resources/{case_id}-directory/consult").status_code == 303
    for reference in ("29 WC", "68 WC", "92 WC"):
        assert client.post(f"/investigations/{session_id}/leads", data={"reference": reference}).status_code == 303
    lodging = next(lead for lead in registry.snapshot(session_id).leads if lead.reference == "68 WC")
    assert client.post(f"/investigations/{session_id}/leads/{lodging.lead_id}/visit").status_code == 303
    visit_id = registry.snapshot(session_id).visits[-1].visit_id
    confirmation_page = client.get(f"/investigations/{session_id}?lead={lodging.lead_id}")
    assert confirmation_page.text.count('value="break-in"') == 1
    assert confirmation_page.text.index('class="thread-stream"') < confirmation_page.text.index('value="break-in"')
    assert 'disabled>Continue discussion</button>' not in confirmation_page.text
    assert confirmation_page.text.index('>Continue discussion</button>') < confirmation_page.text.index('Generate one bounded investigator exchange')
    assert client.post(
        f"/investigations/{session_id}/visits/{visit_id}/interaction",
        data={"interaction_id": "break-in"},
    ).status_code == 303
    mid = registry.snapshot(session_id)
    assert "wc-68" in mid.case_state.closed_lead_keys
    assert mid.case_state.continuation_visit_id == visit_id
    choice_page = client.get(f"/investigations/{session_id}?lead={lodging.lead_id}")
    assert choice_page.text.count('value="burn-uniform"') == 1
    assert choice_page.text.index('value="burn-uniform"') < choice_page.text.index('class="thread-stream"')
    assert 'name="option_id" required' in choice_page.text
    assert 'value="footman"' in choice_page.text
    assert '<button class="primary-action" type="submit">Confirm action</button>' in choice_page.text
    assert 'disabled>Continue discussion</button>' in choice_page.text
    assert client.post(
        f"/investigations/{session_id}/visits/{visit_id}/interaction",
        data={"interaction_id": "burn-uniform", "option_id": "footman"},
    ).status_code == 303
    completed_visit = registry.snapshot(session_id)
    assert completed_visit.case_state.continuation_visit_id is None
    resolved_page = client.get(f"/investigations/{session_id}?lead={lodging.lead_id}")
    assert 'disabled>Continue discussion</button>' not in resolved_page.text
    assert len([entry for entry in completed_visit.case_state.accounting_entries if entry.source_kind == "first-visit"]) == 3
    assert client.post(f"/investigations/{session_id}/leads/{lodging.lead_id}/visit").status_code == 409
    assert client.post(f"/investigations/{session_id}/conclusion/start").status_code == 303
    assert client.post(f"/investigations/{session_id}/conclusion/drafts").status_code == 303
    assert client.post(f"/investigations/{session_id}/conclusion/lock").status_code == 303
    assert client.post(f"/investigations/{session_id}/conclusion/answer-elements").status_code == 303
    assert client.post(f"/investigations/{session_id}/conclusion/score", data={}).status_code == 303
    assert registry.snapshot(session_id).conclusion.score_result.score_band_text == "At least you tried."
    assert client.post(f"/investigations/{session_id}/conclusion/solution").status_code == 303
    assert registry.snapshot(session_id).status.value == "completed"


def test_private_conclusion_files_are_opened_only_at_the_permitted_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads: list[str] = []
    original = Path.read_text

    def recording_read(path: Path, *args, **kwargs):
        reads.append(str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", recording_read)
    app = create_app(project_root=ROOT, output_root=tmp_path / "outputs")
    with ASGITestClient(app) as client:
        session_id = create_demo(client)
        assert not any("conclusions/private/" in path for path in reads)
        for endpoint in ("start", "drafts"):
            assert client.post(f"/investigations/{session_id}/conclusion/{endpoint}").status_code == 303
        assert client.post(f"/investigations/{session_id}/conclusion/lock").status_code == 303
        assert not any("conclusions/private/" in path for path in reads)
        assert client.post(f"/investigations/{session_id}/conclusion/answer-elements").status_code == 303
        assert any("conclusions/private/scoring/" in path for path in reads)
        assert not any("conclusions/private/solutions/" in path for path in reads)
        assert client.post(f"/investigations/{session_id}/conclusion/score", data={}).status_code == 303
        assert not any("conclusions/private/solutions/" in path for path in reads)
        assert client.post(f"/investigations/{session_id}/conclusion/solution").status_code == 303
        assert any("conclusions/private/solutions/" in path for path in reads)


def test_demo3_modes_budget_brooch_and_authored_terminal_flow(authored_web) -> None:
    client, registry = authored_web
    case_id = "demo-3-the-disappearance-of-a-student"
    session_id = create_demo(client, case_id)
    assert client.post(
        f"/investigations/{session_id}/leads",
        data={"reference": "2000", "mode": "interview"},
    ).status_code == 303
    assert registry.snapshot(session_id).case_state.lead_budget_remaining == 12
    for reference, mode in (
        ("1200", "interview"),
        ("1300", "interview"),
        ("1340", "interview"),
        ("1400", "interview"),
        ("1922", "interview"),
        ("1931", "interview"),
        ("1932", "interview"),
        ("2010", "interview"),
        ("1921", "investigation"),
        ("1926", "interview"),
        ("1927", "investigation"),
        ("2005", "interview"),
    ):
        response = client.post(f"/investigations/{session_id}/leads", data={"reference": reference, "mode": mode})
        assert response.status_code == 303, (reference, mode, response.text)
    exhausted = registry.snapshot(session_id)
    assert exhausted.case_state.lead_budget_remaining == 0
    assert "rose_brooch" in exhausted.case_state.items
    assert client.post(f"/investigations/{session_id}/leads", data={"reference": "1900", "mode": "intervention"}).status_code == 303
    ended = registry.snapshot(session_id)
    assert ended.status.value == "completed"
    assert ended.case_state.outcome == "mission_completed"
    assert ended.final_theory is None and ended.conclusion is None
    page = client.get(f"/investigations/{session_id}")
    assert "Authored outcome" in page.text
    assert "You have completed your mission" in page.text
    assert "Official conclusion" not in page.text
