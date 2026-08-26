"""HTTP tests for investigation creation and canonical session rendering."""

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.asgi_client import ASGITestClient

import multi_agent_personalities.web.investigation_routes as investigation_routes
from multi_agent_personalities.application import (
    StructuredOutputError,
    build_investigation_mock_runtime,
    reveal_clue,
)
from multi_agent_personalities.models import (
    InvestigationRoundStatus,
    InvestigationStatus,
)
from multi_agent_personalities.web.app import create_app
from multi_agent_personalities.web.investigation_routes import (
    MAX_CASE_INTRODUCTION_LENGTH,
    MAX_CLUE_LENGTH,
    _validate_investigation_creation_form,
)
from multi_agent_personalities.web.investigation_store import (
    InMemoryInvestigationRegistry,
    InvestigationRegistryInvariantError,
    InvestigationSessionCollisionError,
    InvestigationSessionRecord,
)
from tests.test_investigation_workflow_e2e import run_two_round_workflow


ROOT = Path(__file__).resolve().parents[1]
INTRODUCTION = "A researcher disappears from a locked archive room."
VALID_FORM = {
    "characters": ["sherlock", "poirot"],
    "introduction": INTRODUCTION,
}


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)


@pytest.fixture
def investigation_client(
    tmp_path: Path,
) -> Iterator[tuple[ASGITestClient, InMemoryInvestigationRegistry, Path]]:
    registry = InMemoryInvestigationRegistry()
    output_root = tmp_path / "outputs"
    application = create_app(
        project_root=ROOT,
        output_root=output_root,
        investigation_registry=registry,
    )
    assert application.state.investigation_registry is registry
    with ASGITestClient(application) as client:
        yield client, registry, output_root


def assert_html(response: Any, status_code: int) -> None:
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("text/html")


def assert_no_output(output_root: Path) -> None:
    assert not output_root.exists()


def advance_first_session_to_discussion(client: ASGITestClient) -> None:
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations/session_001/clues",
        data={"clue": "The study window was open."},
    )
    response = client.post("/investigations/session_001/analyses")
    assert response.status_code == 303


def advance_first_session_to_decision(client: ASGITestClient) -> None:
    advance_first_session_to_discussion(client)
    response = client.post("/investigations/session_001/discussion")
    assert response.status_code == 303


def test_index_is_side_effect_free_and_catalogue_driven(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, output_root = investigation_client

    response = client.get("/investigations")

    assert_html(response, 200)
    assert registry.session_ids == ()
    assert "New investigation session" in response.text
    assert "Sherlock Holmes" in response.text
    assert "Hercule Poirot" in response.text
    assert "acute observation" in response.text
    assert "psychological insight" in response.text
    assert 'name="introduction"' in response.text
    assert f'maxlength="{MAX_CASE_INTRODUCTION_LENGTH}"' in response.text
    assert 'method="post"' in response.text
    assert "/investigations" in response.text
    assert "Offline deterministic mock" in response.text
    assert "No investigations in this process" in response.text
    assert 'href="http://testserver/"' in response.text
    assert_no_output(output_root)


def test_valid_creation_uses_303_prg_and_renders_empty_snapshot(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, output_root = investigation_client

    response = client.post("/investigations", data=VALID_FORM)

    assert response.status_code == 303
    assert response.headers["location"] == "/investigations/session_001"
    assert registry.session_ids == ("session_001",)
    record = registry.get("session_001")
    assert record.session.status is InvestigationStatus.ACTIVE
    assert record.session.clues == record.session.rounds == ()
    assert record.session.analyses == record.session.decisions == ()
    assert record.session.final_theory is None
    assert record.runtime.id_factory.session_id == "session_001"

    detail = client.get(response.headers["location"])
    assert_html(detail, 200)
    assert "session_001" in detail.text
    assert INTRODUCTION in detail.text
    assert "Sherlock Holmes" in detail.text
    assert "Hercule Poirot" in detail.text
    assert "ACTIVE" in detail.text
    assert "Awaiting first clue" in detail.text
    assert "Waiting for the Game Master to reveal the first clue." in detail.text
    assert "No clues revealed" in detail.text
    assert 'action="http://testserver/investigations/session_001/clues"' in detail.text
    assert 'method="post"' in detail.text
    assert 'name="clue"' in detail.text
    assert f'maxlength="{MAX_CLUE_LENGTH}"' in detail.text
    for suffix in ("analyses", "discussion", "decision", "finalize"):
        assert f"/investigations/session_001/{suffix}" not in detail.text
    assert_no_output(output_root)


def test_first_clue_uses_303_prg_and_waits_for_analyses(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, output_root = investigation_client
    client.post("/investigations", data=VALID_FORM)
    before = registry.get("session_001")
    runtime = before.runtime
    clue_text = "The archive-room window was found open."

    response = client.post(
        "/investigations/session_001/clues",
        data={"clue": clue_text},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/investigations/session_001"
    assert registry.session_ids == ("session_001",)
    updated = registry.get("session_001")
    assert updated.runtime is runtime
    assert len(updated.session.clues) == len(updated.session.rounds) == 1
    assert updated.session.clues[0].text == clue_text
    assert updated.session.rounds[0].status is (
        InvestigationRoundStatus.AWAITING_ANALYSES
    )

    detail = client.get(response.headers["location"])
    assert_html(detail, 200)
    assert clue_text in detail.text
    assert "Clue 1 · Round 1" in detail.text
    assert "Round 1" in detail.text
    assert "Waiting for independent analyses." in detail.text
    assert "Run independent analyses" in detail.text
    assert (
        'action="http://testserver/investigations/session_001/analyses"'
        in detail.text
    )
    assert (
        'action="http://testserver/investigations/session_001/clues"'
        not in detail.text
    )
    for _ in range(2):
        assert client.get(response.headers["location"]).status_code == 200
    assert registry.get("session_001") is updated
    assert registry.session_ids == ("session_001",)
    assert_no_output(output_root)


def test_first_round_analyses_use_303_prg_and_render_reasoning(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, output_root = investigation_client
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations/session_001/clues",
        data={"clue": "The study window was open."},
    )
    before = registry.get("session_001")
    runtime = before.runtime

    response = client.post("/investigations/session_001/analyses")

    assert response.status_code == 303
    assert response.headers["location"] == "/investigations/session_001"
    updated = registry.get("session_001")
    assert updated.runtime is runtime
    assert updated.session.clues == before.session.clues
    assert len(updated.session.rounds) == 1
    current_round = updated.session.rounds[-1]
    assert current_round.status is InvestigationRoundStatus.AWAITING_DISCUSSION
    assert tuple(item.agent_id for item in updated.session.analyses) == (
        updated.session.participant_ids
    )
    assert current_round.analysis_ids == tuple(
        item.analysis_id for item in updated.session.analyses
    )
    assert all(
        item.round_id == current_round.round_id
        for item in updated.session.analyses
    )
    assert len(updated.session.hypotheses) == 1
    assert updated.session.hypotheses[0].round_id == current_round.round_id

    detail = client.get(response.headers["location"])
    assert_html(detail, 200)
    assert "Waiting for group discussion." in detail.text
    assert detail.text.index("SHERLOCK_R1") < detail.text.index("POIROT_R1")
    assert "Facts" in detail.text
    assert "Deductions" in detail.text
    assert "Supports — Clue 1" in detail.text
    assert "Proposed leads" in detail.text
    assert "Inspect the ground beneath the window." in detail.text
    assert "Hypotheses proposed in Round 1" in detail.text
    assert "The visitor left through the study window." in detail.text
    assert "Sherlock hypotheses" not in detail.text
    assert "Poirot hypotheses" not in detail.text
    assert "Run independent analyses" not in detail.text
    assert "Run group discussion" in detail.text
    assert (
        'action="http://testserver/investigations/session_001/discussion"'
        in detail.text
    )
    assert "runs 2 ordered discussion turns" in detail.text
    for suffix in ("decision", "finalize"):
        assert f"/investigations/session_001/{suffix}" not in detail.text
    for _ in range(2):
        assert client.get(response.headers["location"]).status_code == 200
    assert registry.get("session_001") is updated
    assert_no_output(output_root)


def test_first_round_discussion_uses_303_prg_and_renders_stored_order(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, output_root = investigation_client
    advance_first_session_to_discussion(client)
    before = registry.get("session_001")
    runtime = before.runtime
    analyses = before.session.analyses
    hypotheses = before.session.hypotheses

    response = client.post("/investigations/session_001/discussion")

    assert response.status_code == 303
    assert response.headers["location"] == "/investigations/session_001"
    updated = registry.get("session_001")
    assert updated.runtime is runtime
    assert updated.session.clues == before.session.clues
    assert updated.session.analyses == analyses
    assert updated.session.hypotheses == hypotheses
    current_round = updated.session.rounds[-1]
    assert current_round.status is InvestigationRoundStatus.AWAITING_DECISION
    discussion = current_round.discussion_run
    assert discussion is not None
    assert len(discussion.messages) == runtime.capabilities.discussion_turns
    assert tuple(item.speaker_character_id for item in discussion.messages) == (
        updated.session.participant_ids
    )

    detail = client.get(response.headers["location"])
    assert_html(detail, 200)
    assert "Waiting for a group decision." in detail.text
    assert "Round 1 discussion" in detail.text
    assert detail.text.index("SHERLOCK_DISCUSSION_R1") < detail.text.index(
        "POIROT_DISCUSSION_R1"
    )
    assert "Sherlock Holmes" in detail.text
    assert "Hercule Poirot" in detail.text
    assert "Run group discussion" not in detail.text
    assert "Create group decision" in detail.text
    assert (
        'action="http://testserver/investigations/session_001/decision"'
        in detail.text
    )
    assert "/investigations/session_001/finalize" not in detail.text
    for _ in range(2):
        assert client.get(response.headers["location"]).status_code == 200
    assert registry.get("session_001") is updated
    assert_no_output(output_root)


def test_first_round_decision_uses_303_prg_and_pauses_for_game_master(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, output_root = investigation_client
    advance_first_session_to_decision(client)
    before = registry.get("session_001")
    runtime = before.runtime
    clues = before.session.clues
    analyses = before.session.analyses
    hypotheses = before.session.hypotheses
    discussion = before.session.rounds[-1].discussion_run

    response = client.post("/investigations/session_001/decision")

    assert response.status_code == 303
    assert response.headers["location"] == "/investigations/session_001"
    updated = registry.get("session_001")
    assert updated.runtime is runtime
    assert updated.session.status is InvestigationStatus.ACTIVE
    assert updated.session.clues == clues
    assert updated.session.analyses == analyses
    assert updated.session.hypotheses == hypotheses
    assert len(updated.session.clues) == len(updated.session.rounds) == 1
    assert len(updated.session.decisions) == 1
    current_round = updated.session.rounds[-1]
    decision = updated.session.decisions[-1]
    assert current_round.status is InvestigationRoundStatus.COMPLETED
    assert current_round.decision_id == decision.decision_id
    assert decision.round_id == current_round.round_id
    assert current_round.discussion_run == discussion
    assert updated.session.final_theory is None

    detail = client.get(response.headers["location"])
    assert_html(detail, 200)
    assert "Waiting for the Game Master to reveal the next clue." in detail.text
    assert "Round 1 group decision" in detail.text
    assert "Pursue Lead" in detail.text
    assert "Inspect the ground below the window" in detail.text
    assert "Sherlock Holmes — Round 1 analysis" in detail.text
    assert "Hercule Poirot — Round 1 analysis" in detail.text
    assert "The visitor left through the study window." in detail.text
    assert "Context — Clue 1" in detail.text
    assert 'name="clue"' in detail.text
    assert "Create group decision" not in detail.text
    assert "/investigations/session_001/finalize" not in detail.text
    for _ in range(2):
        assert client.get(response.headers["location"]).status_code == 200
    assert registry.get("session_001") is updated
    assert len(updated.session.clues) == len(updated.session.rounds) == 1
    assert_no_output(output_root)


def test_decision_before_discussion_is_409_without_mutation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    client.post("/investigations", data=VALID_FORM)
    states = [registry.get("session_001")]
    client.post(
        "/investigations/session_001/clues",
        data={"clue": "The study window was open."},
    )
    states.append(registry.get("session_001"))
    client.post("/investigations/session_001/analyses")
    states.append(registry.get("session_001"))

    for state in states:
        isolated = InMemoryInvestigationRegistry()
        isolated.register(state)
        app = create_app(
            project_root=ROOT,
            investigation_registry=isolated,
        )
        response = ASGITestClient(app).post(
            "/investigations/session_001/decision"
        )
        assert_html(response, 409)
        assert isolated.get("session_001") is state


def test_repeated_decision_is_409_and_keeps_committed_record(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    advance_first_session_to_decision(client)
    client.post("/investigations/session_001/decision")
    committed = registry.get("session_001")

    response = client.post("/investigations/session_001/decision")

    assert_html(response, 409)
    assert registry.get("session_001") is committed
    assert len(committed.session.decisions) == 1
    assert len(committed.session.hypotheses) == 1


@pytest.mark.parametrize("session_id", ["bad$id", "session_999"])
def test_decision_post_to_malformed_or_unknown_session_is_404(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    session_id: str,
) -> None:
    client, registry, output_root = investigation_client

    response = client.post(f"/investigations/{session_id}/decision")

    assert_html(response, 404)
    assert "Traceback" not in response.text
    assert registry.session_ids == ()
    assert_no_output(output_root)


@pytest.mark.parametrize(
    "failure",
    [
        StructuredOutputError("private malformed decision JSON"),
        FileNotFoundError("/private/decision-fixture.json"),
        ValueError("private invalid decision reference"),
    ],
)
def test_decision_failures_are_safe_500_and_atomic(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    client, registry, output_root = investigation_client
    advance_first_session_to_decision(client)
    before = registry.get("session_001")

    def fail(*args: object, **kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(investigation_routes, "create_group_decision", fail)
    response = client.post("/investigations/session_001/decision")

    assert_html(response, 500)
    assert response.status_code != 409
    assert "unexpected local generation error" in response.text
    assert "private" not in response.text
    assert "Traceback" not in response.text
    assert registry.get("session_001") is before
    assert before.session.rounds[-1].status is (
        InvestigationRoundStatus.AWAITING_DECISION
    )
    assert before.session.decisions == ()
    assert len(before.session.hypotheses) == 1
    assert_no_output(output_root)


def test_second_round_decision_preserves_history_and_pauses_exhausted(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    trace = run_two_round_workflow()
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"),
        session_sequence=1,
        project_root=ROOT,
    )
    before = registry.register(
        InvestigationSessionRecord(
            session_sequence=1,
            session=trace.round_two_discussion.session,
            runtime=runtime,
        )
    )
    first_round = before.session.rounds[0]
    first_decision = before.session.decisions[0]

    response = client.post("/investigations/session_001/decision")

    assert response.status_code == 303
    updated = registry.get("session_001")
    assert updated.runtime is runtime
    assert updated.session.rounds[0] == first_round
    assert updated.session.decisions[0] == first_decision
    assert len(updated.session.decisions) == 2
    assert updated.session.rounds[1].status is InvestigationRoundStatus.COMPLETED
    assert updated.session.decisions[1].round_id == updated.session.rounds[1].round_id
    assert updated.session.status is InvestigationStatus.ACTIVE
    assert updated.session.final_theory is None
    detail = client.get(response.headers["location"])
    assert "Round 1 group decision" in detail.text
    assert "Round 2 group decision" in detail.text
    assert "Adopt Hypothesis" in detail.text
    assert "no more clue rounds available" in detail.text
    assert 'name="clue"' not in detail.text
    assert "Create group decision" not in detail.text
    assert "/investigations/session_001/finalize" not in detail.text


def test_session_two_decision_namespace_and_isolation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations",
        data={**VALID_FORM, "introduction": "Second decision case."},
    )
    first_before = registry.get("session_001")
    client.post(
        "/investigations/session_002/clues",
        data={"clue": "A clue scoped to session two."},
    )
    client.post("/investigations/session_002/analyses")
    client.post("/investigations/session_002/discussion")

    response = client.post("/investigations/session_002/decision")

    assert response.status_code == 303
    assert registry.get("session_001") is first_before
    second = registry.get("session_002")
    serialized = second.session.model_dump_json()
    assert len(second.session.decisions) == 1
    assert "session_002_decision_0001" in serialized
    assert "session_001_" not in serialized


def test_decision_summary_is_html_escaped(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    trace = run_two_round_workflow()
    payload = trace.round_one_decision.session.model_dump(mode="python")
    payload["decisions"][0]["summary"] = "<script>decision()</script>"
    escaped_session = type(trace.round_one_decision.session).model_validate(payload)
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"),
        session_sequence=1,
        project_root=ROOT,
    )
    registry.register(
        InvestigationSessionRecord(
            session_sequence=1,
            session=escaped_session,
            runtime=runtime,
        )
    )

    detail = client.get("/investigations/session_001")

    assert "<script>decision()" not in detail.text
    assert "&lt;script&gt;decision()&lt;/script&gt;" in detail.text


def test_discussion_before_analyses_is_409_without_mutation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    client.post("/investigations", data=VALID_FORM)
    empty = registry.get("session_001")
    response = client.post("/investigations/session_001/discussion")
    assert_html(response, 409)
    assert registry.get("session_001") is empty

    client.post(
        "/investigations/session_001/clues",
        data={"clue": "The study window was open."},
    )
    awaiting = registry.get("session_001")
    response = client.post("/investigations/session_001/discussion")
    assert_html(response, 409)
    assert registry.get("session_001") is awaiting
    assert awaiting.session.rounds[-1].discussion_run is None


def test_repeated_discussion_is_409_and_keeps_committed_record(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    advance_first_session_to_discussion(client)
    client.post("/investigations/session_001/discussion")
    committed = registry.get("session_001")

    response = client.post("/investigations/session_001/discussion")

    assert_html(response, 409)
    assert registry.get("session_001") is committed
    assert committed.session.rounds[-1].discussion_run is not None


@pytest.mark.parametrize("session_id", ["bad$id", "session_999"])
def test_discussion_post_to_malformed_or_unknown_session_is_404(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    session_id: str,
) -> None:
    client, registry, output_root = investigation_client

    response = client.post(f"/investigations/{session_id}/discussion")

    assert_html(response, 404)
    assert "Traceback" not in response.text
    assert registry.session_ids == ()
    assert_no_output(output_root)


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("/private/discussion-fixture.txt"),
        ValueError("private mock discussion task mismatch"),
        RuntimeError("private simulation failure"),
    ],
)
def test_discussion_failures_are_safe_500_and_atomic(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    client, registry, output_root = investigation_client
    advance_first_session_to_discussion(client)
    before = registry.get("session_001")

    def fail(*args: object, **kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(investigation_routes, "run_group_discussion", fail)
    response = client.post("/investigations/session_001/discussion")

    assert_html(response, 500)
    assert response.status_code != 409
    assert "unexpected local generation error" in response.text
    assert "private" not in response.text
    assert "Traceback" not in response.text
    assert registry.get("session_001") is before
    assert before.session.rounds[-1].status is (
        InvestigationRoundStatus.AWAITING_DISCUSSION
    )
    assert before.session.rounds[-1].discussion_run is None
    assert_no_output(output_root)


@pytest.mark.parametrize(
    "trace_attribute",
    ["round_one_discussion", "round_one_decision", "finalization"],
)
def test_discussion_wrong_later_phase_is_409_without_mutation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    trace_attribute: str,
) -> None:
    client, registry, _ = investigation_client
    trace = run_two_round_workflow()
    snapshot = getattr(trace, trace_attribute)
    session = getattr(snapshot, "session", snapshot)
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"),
        session_sequence=1,
        project_root=ROOT,
    )
    before = registry.register(
        InvestigationSessionRecord(
            session_sequence=1,
            session=session,
            runtime=runtime,
        )
    )

    response = client.post("/investigations/session_001/discussion")

    assert_html(response, 409)
    assert registry.get("session_001") is before


def test_second_round_discussion_preserves_first_round_history(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    trace = run_two_round_workflow()
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"),
        session_sequence=1,
        project_root=ROOT,
    )
    before = registry.register(
        InvestigationSessionRecord(
            session_sequence=1,
            session=trace.round_two_analyses.session,
            runtime=runtime,
        )
    )
    first_discussion = before.session.rounds[0].discussion_run

    response = client.post("/investigations/session_001/discussion")

    assert response.status_code == 303
    updated = registry.get("session_001")
    assert updated.runtime is runtime
    assert updated.session.rounds[0].discussion_run == first_discussion
    assert updated.session.rounds[1].discussion_run is not None
    assert updated.session.rounds[1].status is (
        InvestigationRoundStatus.AWAITING_DECISION
    )
    detail = client.get(response.headers["location"])
    assert "Round 1 discussion" in detail.text
    assert "Round 2 discussion" in detail.text
    assert "Waiting for a group decision." in detail.text
    assert "no more clue rounds available" not in detail.text


def test_session_two_discussion_namespace_and_isolation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations",
        data={**VALID_FORM, "introduction": "Second discussion case."},
    )
    first_before = registry.get("session_001")
    client.post(
        "/investigations/session_002/clues",
        data={"clue": "A clue scoped to session two."},
    )
    client.post("/investigations/session_002/analyses")

    response = client.post("/investigations/session_002/discussion")

    assert response.status_code == 303
    assert registry.get("session_001") is first_before
    second = registry.get("session_002")
    serialized = second.session.model_dump_json()
    assert second.session.rounds[-1].discussion_run is not None
    assert "session_002_round_0001_discussion" in serialized
    assert "session_001_" not in serialized


def test_discussion_message_text_is_html_escaped(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    trace = run_two_round_workflow()
    payload = trace.round_one_discussion.session.model_dump(mode="python")
    payload["rounds"][0]["discussion_run"]["messages"][0]["text"] = (
        "<script>discussion()</script>"
    )
    escaped_session = type(trace.round_one_discussion.session).model_validate(
        payload
    )
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"),
        session_sequence=1,
        project_root=ROOT,
    )
    registry.register(
        InvestigationSessionRecord(
            session_sequence=1,
            session=escaped_session,
            runtime=runtime,
        )
    )

    detail = client.get("/investigations/session_001")

    assert "<script>discussion()" not in detail.text
    assert "&lt;script&gt;discussion()&lt;/script&gt;" in detail.text


def test_analyses_before_a_clue_are_409_without_mutation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    client.post("/investigations", data=VALID_FORM)
    before = registry.get("session_001")

    response = client.post("/investigations/session_001/analyses")

    assert_html(response, 409)
    assert "cannot run" in response.text
    assert registry.get("session_001") is before
    assert before.session.rounds == before.session.analyses == ()


def test_repeated_analyses_are_409_and_keep_committed_record(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations/session_001/clues",
        data={"clue": "The study window was open."},
    )
    client.post("/investigations/session_001/analyses")
    committed = registry.get("session_001")

    response = client.post("/investigations/session_001/analyses")

    assert_html(response, 409)
    assert registry.get("session_001") is committed
    assert len(committed.session.analyses) == 2
    assert len(committed.session.hypotheses) == 1


@pytest.mark.parametrize("session_id", ["bad$id", "session_999"])
def test_analysis_post_to_malformed_or_unknown_session_is_404(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    session_id: str,
) -> None:
    client, registry, output_root = investigation_client

    response = client.post(f"/investigations/{session_id}/analyses")

    assert_html(response, 404)
    assert "Traceback" not in response.text
    assert registry.session_ids == ()
    assert_no_output(output_root)


@pytest.mark.parametrize(
    "failure",
    [
        StructuredOutputError("private malformed generated JSON"),
        FileNotFoundError("/private/fixture/path.json"),
        ValueError("private provider metadata mismatch"),
    ],
)
def test_analysis_generation_failures_are_safe_500_and_atomic(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    client, registry, output_root = investigation_client
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations/session_001/clues",
        data={"clue": "The study window was open."},
    )
    before = registry.get("session_001")

    def fail(*args: object, **kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(investigation_routes, "run_independent_analyses", fail)
    response = client.post("/investigations/session_001/analyses")

    assert_html(response, 500)
    assert response.status_code != 409
    assert "unexpected local generation error" in response.text
    assert "private" not in response.text
    assert "Traceback" not in response.text
    assert registry.get("session_001") is before
    assert before.session.analyses == before.session.hypotheses == ()
    assert before.session.rounds[-1].analysis_ids == ()
    assert_no_output(output_root)


@pytest.mark.parametrize(
    "trace_attribute",
    [
        "round_one_analyses",
        "round_one_discussion",
        "round_one_decision",
        "finalization",
    ],
)
def test_analysis_wrong_later_phase_is_409_without_mutation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    trace_attribute: str,
) -> None:
    client, registry, _ = investigation_client
    trace = run_two_round_workflow()
    snapshot = getattr(trace, trace_attribute)
    session = getattr(snapshot, "session", snapshot)
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"),
        session_sequence=1,
        project_root=ROOT,
    )
    before = registry.register(
        InvestigationSessionRecord(
            session_sequence=1,
            session=session,
            runtime=runtime,
        )
    )

    response = client.post("/investigations/session_001/analyses")

    assert_html(response, 409)
    assert registry.get("session_001") is before


def test_second_round_analyses_preserve_first_round_history(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    trace = run_two_round_workflow()
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"),
        session_sequence=1,
        project_root=ROOT,
    )
    before = registry.register(
        InvestigationSessionRecord(
            session_sequence=1,
            session=trace.round_two_revealed,
            runtime=runtime,
        )
    )
    round_one_analyses = before.session.analyses

    response = client.post("/investigations/session_001/analyses")

    assert response.status_code == 303
    updated = registry.get("session_001")
    assert updated.runtime is runtime
    assert updated.session.analyses[:2] == round_one_analyses
    assert len(updated.session.analyses) == 4
    assert all(
        item.round_id == updated.session.rounds[1].round_id
        for item in updated.session.analyses[2:]
    )
    assert updated.session.rounds[1].status is (
        InvestigationRoundStatus.AWAITING_DISCUSSION
    )
    detail = client.get(response.headers["location"])
    assert "Round 1 analyses" in detail.text
    assert "Round 2 analyses" in detail.text
    assert "Waiting for group discussion." in detail.text
    assert "no more clue rounds available" not in detail.text
    assert 'name="clue"' not in detail.text


def test_session_two_analysis_namespace_and_isolation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations",
        data={**VALID_FORM, "introduction": "Second namespace case."},
    )
    first_before = registry.get("session_001")
    client.post(
        "/investigations/session_002/clues",
        data={"clue": "A clue scoped to session two."},
    )

    response = client.post("/investigations/session_002/analyses")

    assert response.status_code == 303
    assert registry.get("session_001") is first_before
    second = registry.get("session_002")
    serialized = second.session.model_dump_json()
    assert len(second.session.analyses) == 2
    assert "session_002_analysis_" in serialized
    assert "session_002_hypothesis_" in serialized
    assert "session_001_" not in serialized


def test_unsupported_third_round_analysis_is_409_before_generation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    trace = run_two_round_workflow()
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"),
        session_sequence=1,
        project_root=ROOT,
    )
    third_round = reveal_clue(
        trace.round_two_decision.session,
        clue_text="A domain-valid clue beyond the mock fixture capability.",
        id_factory=runtime.id_factory,
    )
    before = registry.register(
        InvestigationSessionRecord(
            session_sequence=1,
            session=third_round,
            runtime=runtime,
        )
    )

    response = client.post("/investigations/session_001/analyses")

    assert_html(response, 409)
    assert registry.get("session_001") is before
    assert before.session.rounds[-1].round_index == 3
    assert before.session.analyses == trace.round_two_decision.session.analyses


def test_generated_reasoning_text_is_html_escaped(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    trace = run_two_round_workflow()
    payload = trace.round_one_analyses.session.model_dump(mode="python")
    payload["analyses"][0]["facts"] = ("<script>analysis()</script>",)
    payload["hypotheses"][0]["statement"] = "<img src=x onerror=theory()>"
    escaped_session = type(trace.round_one_analyses.session).model_validate(payload)
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"),
        session_sequence=1,
        project_root=ROOT,
    )
    registry.register(
        InvestigationSessionRecord(
            session_sequence=1,
            session=escaped_session,
            runtime=runtime,
        )
    )

    detail = client.get("/investigations/session_001")

    assert "<script>analysis()" not in detail.text
    assert "&lt;script&gt;analysis()&lt;/script&gt;" in detail.text
    assert "<img src=x" not in detail.text
    assert "&lt;img src=x onerror=theory()&gt;" in detail.text


@pytest.mark.parametrize(
    ("data", "message", "preserved"),
    [
        ({}, "Enter a clue.", None),
        ({"clue": "   "}, "Enter a clue.", None),
        (
            {"clue": "x" * (MAX_CLUE_LENGTH + 1)},
            f"at most {MAX_CLUE_LENGTH} characters",
            "xxxxx",
        ),
    ],
)
def test_clue_input_errors_are_400_without_mutation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    data: dict[str, str],
    message: str,
    preserved: str | None,
) -> None:
    client, registry, output_root = investigation_client
    client.post("/investigations", data=VALID_FORM)
    before = registry.get("session_001")

    response = client.post("/investigations/session_001/clues", data=data)

    assert_html(response, 400)
    assert message in response.text
    if preserved is not None:
        assert preserved in response.text
    assert registry.get("session_001") is before
    assert_no_output(output_root)


def test_revealed_clue_is_html_escaped(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, _, _ = investigation_client
    client.post("/investigations", data=VALID_FORM)
    clue = "<script>alert('clue')</script>"
    client.post("/investigations/session_001/clues", data={"clue": clue})

    detail = client.get("/investigations/session_001")

    assert clue not in detail.text
    assert "&lt;script&gt;alert" in detail.text
    assert "&lt;/script&gt;" in detail.text
    assert "<script" not in detail.text


@pytest.mark.parametrize("session_id", ["bad$id", "session_999"])
def test_clue_post_to_malformed_or_unknown_session_is_404(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    session_id: str,
) -> None:
    client, registry, output_root = investigation_client

    response = client.post(
        f"/investigations/{session_id}/clues",
        data={"clue": "A valid clue."},
    )

    assert_html(response, 404)
    assert registry.session_ids == ()
    assert_no_output(output_root)


def test_repeated_clue_while_round_incomplete_is_409_and_atomic(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations/session_001/clues",
        data={"clue": "First clue."},
    )
    committed = registry.get("session_001")

    response = client.post(
        "/investigations/session_001/clues",
        data={"clue": "Repeated clue."},
    )

    assert_html(response, 409)
    assert "cannot accept a clue" in response.text
    assert registry.get("session_001") is committed
    assert len(committed.session.clues) == len(committed.session.rounds) == 1


def _register_completed_mock_record(
    registry: InMemoryInvestigationRegistry,
    *,
    completed_session: bool,
) -> InvestigationSessionRecord:
    trace = run_two_round_workflow()
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"),
        session_sequence=1,
        project_root=ROOT,
    )
    session = (
        trace.finalization.session
        if completed_session
        else trace.round_two_decision.session
    )
    return registry.register(
        InvestigationSessionRecord(
            session_sequence=1,
            session=session,
            runtime=runtime,
        )
    )


@pytest.mark.parametrize(
    ("trace_attribute", "expected_message"),
    [
        ("round_two_revealed", "Waiting for independent analyses."),
        ("round_two_analyses", "Waiting for group discussion."),
        ("round_two_discussion", "Waiting for a group decision."),
    ],
)
def test_active_second_round_preserves_current_workflow_message(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    trace_attribute: str,
    expected_message: str,
) -> None:
    client, registry, _ = investigation_client
    trace = run_two_round_workflow()
    snapshot = getattr(trace, trace_attribute)
    session = getattr(snapshot, "session", snapshot)
    runtime = build_investigation_mock_runtime(
        character_slugs=("sherlock", "poirot"),
        session_sequence=1,
        project_root=ROOT,
    )
    registry.register(
        InvestigationSessionRecord(
            session_sequence=1,
            session=session,
            runtime=runtime,
        )
    )

    detail = client.get("/investigations/session_001")

    assert_html(detail, 200)
    assert expected_message in detail.text
    assert "no more clue rounds available" not in detail.text
    assert 'name="clue"' not in detail.text


@pytest.mark.parametrize("completed_session", [False, True])
def test_exhausted_or_completed_session_rejects_clue_without_mutation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    completed_session: bool,
) -> None:
    client, registry, _ = investigation_client
    before = _register_completed_mock_record(
        registry,
        completed_session=completed_session,
    )

    detail = client.get("/investigations/session_001")
    expected_message = (
        "This investigation is completed."
        if completed_session
        else "no more clue rounds available"
    )
    assert expected_message in detail.text
    assert 'name="clue"' not in detail.text

    response = client.post(
        "/investigations/session_001/clues",
        data={"clue": "A forbidden third clue."},
    )

    assert_html(response, 409)
    assert registry.get("session_001") is before
    assert len(before.session.clues) == len(before.session.rounds) == 2


def test_clue_revelation_is_isolated_between_sessions(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    client.post("/investigations", data=VALID_FORM)
    client.post(
        "/investigations",
        data={**VALID_FORM, "introduction": "Second isolated case."},
    )
    second_before = registry.get("session_002")
    client.post(
        "/investigations/session_001/clues",
        data={"clue": "Only the first session sees this clue."},
    )

    assert registry.get("session_002") is second_before
    assert second_before.session.clues == second_before.session.rounds == ()
    second_page = client.get("/investigations/session_002")
    assert "Only the first session sees this clue." not in second_page.text


def test_clue_registry_invariant_failure_is_safe_500(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, registry, _ = investigation_client
    client.post("/investigations", data=VALID_FORM)
    before = registry.get("session_001")

    def fail(*args: object, **kwargs: object) -> None:
        raise InvestigationRegistryInvariantError("private registry detail")

    monkeypatch.setattr(registry, "mutate", fail)
    response = client.post(
        "/investigations/session_001/clues",
        data={"clue": "A valid clue."},
    )

    assert_html(response, 500)
    assert "unexpected local error" in response.text
    assert "private registry detail" not in response.text
    assert "Traceback" not in response.text
    assert registry.get("session_001") is before


def test_second_session_is_namespaced_and_content_isolated(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client
    first_intro = "First isolated case."
    second_intro = "Second isolated case."

    first = client.post(
        "/investigations",
        data={**VALID_FORM, "introduction": first_intro},
    )
    second = client.post(
        "/investigations",
        data={**VALID_FORM, "introduction": second_intro},
    )

    assert first.headers["location"] == "/investigations/session_001"
    assert second.headers["location"] == "/investigations/session_002"
    assert registry.session_ids == ("session_001", "session_002")
    assert registry.get("session_001").runtime.id_factory.session_id == (
        "session_001"
    )
    assert registry.get("session_002").runtime.id_factory.session_id == (
        "session_002"
    )
    first_page = client.get(first.headers["location"])
    second_page = client.get(second.headers["location"])
    assert first_intro in first_page.text and second_intro not in first_page.text
    assert second_intro in second_page.text and first_intro not in second_page.text


def test_app_instances_own_independent_default_registries(tmp_path: Path) -> None:
    first_app = create_app(project_root=ROOT, output_root=tmp_path / "one")
    second_app = create_app(project_root=ROOT, output_root=tmp_path / "two")
    assert first_app.state.investigation_registry is not (
        second_app.state.investigation_registry
    )

    first = ASGITestClient(first_app).post("/investigations", data=VALID_FORM)
    second = ASGITestClient(second_app).post("/investigations", data=VALID_FORM)

    assert first.headers["location"] == "/investigations/session_001"
    assert second.headers["location"] == "/investigations/session_001"


@pytest.mark.parametrize(
    ("data", "error", "preserved"),
    [
        ({"characters": ["sherlock", "poirot"]}, "Enter a case introduction.", None),
        (
            {"characters": ["sherlock", "poirot"], "introduction": "   "},
            "Enter a case introduction.",
            None,
        ),
        (
            {
                "characters": ["sherlock", "poirot"],
                "introduction": "x" * (MAX_CASE_INTRODUCTION_LENGTH + 1),
            },
            f"at most {MAX_CASE_INTRODUCTION_LENGTH} characters",
            "xxxxx",
        ),
        ({"introduction": INTRODUCTION}, "Select all supported investigators.", None),
        (
            {"characters": ["sherlock"], "introduction": INTRODUCTION},
            "Select all supported investigators.",
            None,
        ),
        (
            {
                "characters": ["sherlock", "sherlock"],
                "introduction": INTRODUCTION,
            },
            "Select each investigator only once.",
            None,
        ),
        (
            {
                "characters": ["sherlock", "unknown"],
                "introduction": INTRODUCTION,
            },
            "Select only characters in the current catalogue.",
            None,
        ),
    ],
)
def test_user_form_errors_are_400_and_create_no_session(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    data: dict[str, object],
    error: str,
    preserved: str | None,
) -> None:
    client, registry, output_root = investigation_client

    response = client.post("/investigations", data=data)

    assert_html(response, 400)
    assert error in response.text
    if preserved is not None:
        assert preserved in response.text
    assert registry.session_ids == ()
    assert_no_output(output_root)


def test_known_but_scenario_unsupported_selection_is_user_error() -> None:
    selected, _, _, errors = _validate_investigation_creation_form(
        characters=["sherlock", "third"],
        introduction=INTRODUCTION,
        known_slugs=("sherlock", "poirot", "third"),
        supported_slugs=("sherlock", "poirot"),
    )

    assert selected == ["sherlock"]
    assert errors["characters"] == (
        "Select only investigators supported by the current mock scenario."
    )


def test_reversed_http_order_uses_canonical_runtime_order(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, _ = investigation_client

    response = client.post(
        "/investigations",
        data={
            "characters": ["poirot", "sherlock"],
            "introduction": INTRODUCTION,
        },
    )

    assert response.status_code == 303
    assert registry.get("session_001").session.participant_ids == (
        "sherlock_holmes",
        "hercule_poirot",
    )


@pytest.mark.parametrize("session_id", ["bad$id", "session_999"])
def test_malformed_and_unknown_sessions_render_404_without_mutation(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    session_id: str,
) -> None:
    client, registry, output_root = investigation_client

    response = client.get(f"/investigations/{session_id}")

    assert_html(response, 404)
    assert "Investigation not found" in response.text
    assert "not available in this local process" in response.text
    assert "Traceback" not in response.text
    assert registry.session_ids == ()
    assert_no_output(output_root)


def test_internal_creation_failure_is_safe_500(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, registry, _ = investigation_client

    def fail(**kwargs: object) -> None:
        raise ValueError("private fixture /secret/persona.json is malformed")

    monkeypatch.setattr(registry, "create", fail)
    response = client.post("/investigations", data=VALID_FORM)

    assert_html(response, 500)
    assert "local mock investigation could not be created" in response.text
    assert "/secret/persona.json" not in response.text
    assert "Traceback" not in response.text
    assert registry.session_ids == ()


def test_collision_maps_to_409_without_overwrite(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, registry, _ = investigation_client
    existing = registry.create(
        character_slugs=("sherlock", "poirot"),
        introduction="Existing case.",
        project_root=ROOT,
    )

    def collide(**kwargs: object) -> None:
        raise InvestigationSessionCollisionError("private collision detail")

    monkeypatch.setattr(registry, "create", collide)
    response = client.post("/investigations", data=VALID_FORM)

    assert_html(response, 409)
    assert "identifier is already in use" in response.text
    assert "private collision detail" not in response.text
    assert registry.get(existing.session_id) is existing


def test_repeated_gets_are_side_effect_free_and_do_not_consume_ids(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, output_root = investigation_client
    created = client.post("/investigations", data=VALID_FORM)
    before = registry.get("session_001")

    for _ in range(3):
        assert client.get("/investigations").status_code == 200
        assert client.get(created.headers["location"]).status_code == 200

    assert registry.get("session_001") is before
    second = client.post(
        "/investigations",
        data={**VALID_FORM, "introduction": "Second after GET requests."},
    )
    assert second.headers["location"] == "/investigations/session_002"
    assert_no_output(output_root)


def test_case_introduction_is_html_escaped(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, _, _ = investigation_client
    introduction = "<script>alert('x')</script>"
    created = client.post(
        "/investigations",
        data={**VALID_FORM, "introduction": introduction},
    )

    detail = client.get(created.headers["location"])
    assert introduction not in detail.text
    assert "&lt;script&gt;alert" in detail.text
    assert "&lt;/script&gt;" in detail.text
    assert "<script" not in detail.text


def test_later_investigation_mutation_routes_do_not_exist(
    investigation_client: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, _, _ = investigation_client
    for suffix in ("finalize",):
        response = client.post(f"/investigations/session_001/{suffix}")
        assert response.status_code == 404
