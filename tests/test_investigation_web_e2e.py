"""Complete offline HTTP workflows for the investigation browser delivery."""

import os
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.asgi_client import ASGITestClient

from multi_agent_personalities.models import (
    InvestigationRoundStatus,
    InvestigationSession,
    InvestigationStatus,
)
from multi_agent_personalities.web.app import create_app
from multi_agent_personalities.web.investigation_store import (
    InMemoryInvestigationRegistry,
    InvestigationSessionRecord,
)


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ["sherlock", "poirot"]


@pytest.fixture(autouse=True)
def offline_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the real mock workflow cannot fall through to a live provider."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def reject(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", reject)
    monkeypatch.setattr(socket.socket, "connect", reject)


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
    assert app.state.investigation_registry is registry
    with ASGITestClient(app) as client:
        yield client, registry, output_root


def output_files(output_root: Path) -> tuple[Path, ...]:
    if not output_root.exists():
        return ()
    return tuple(sorted(item for item in output_root.rglob("*") if item.is_file()))


def post_prg(
    client: ASGITestClient,
    session_id: str,
    suffix: str = "",
    *,
    data: dict[str, Any] | None = None,
) -> None:
    path = "/investigations" if not suffix else f"/investigations/{session_id}/{suffix}"
    response = client.post(path, data=data)
    assert response.status_code == 303
    assert response.headers["location"] == f"/investigations/{session_id}"


def get_without_mutation(
    client: ASGITestClient,
    registry: InMemoryInvestigationRegistry,
    session_id: str,
) -> str:
    before = registry.get(session_id)
    response = client.get(f"/investigations/{session_id}")
    assert response.status_code == 200
    assert registry.get(session_id) is before
    return response.text


def round_analyses(session: InvestigationSession, round_id: str) -> tuple[Any, ...]:
    return tuple(item for item in session.analyses if item.round_id == round_id)


def assert_discussion_order(record: InvestigationSessionRecord, index: int) -> None:
    discussion = record.session.rounds[index].discussion_run
    assert discussion is not None
    assert len(discussion.messages) == record.runtime.capabilities.discussion_turns
    assert tuple(item.turn_index for item in discussion.messages) == tuple(
        range(record.runtime.capabilities.discussion_turns)
    )
    assert tuple(item.speaker_character_id for item in discussion.messages) == (
        record.runtime.participant_ids
    )


def assert_structural_namespace(
    session: InvestigationSession,
    own: str,
    other: str,
) -> None:
    prefix = f"{own}_"
    assert session.session_id == own
    assert all(item.clue_id.startswith(prefix) for item in session.clues)
    assert all(
        item.session_id == own and item.round_id.startswith(prefix)
        for item in session.rounds
    )
    assert all(
        item.session_id == own
        and item.analysis_id.startswith(prefix)
        and item.round_id.startswith(prefix)
        for item in session.analyses
    )
    assert all(
        item.session_id == own
        and item.hypothesis_id.startswith(prefix)
        and item.round_id.startswith(prefix)
        for item in session.hypotheses
    )
    assert all(
        item.session_id == own
        and item.decision_id.startswith(prefix)
        and item.round_id.startswith(prefix)
        for item in session.decisions
    )
    evidence = (
        tuple(ref for item in session.analyses for ref in item.evidence)
        + tuple(ref for item in session.hypotheses for ref in item.evidence)
        + tuple(ref for item in session.decisions for ref in item.evidence)
    )
    assert all(ref.clue_id.startswith(prefix) for ref in evidence)
    for investigation_round in session.rounds:
        discussion = investigation_round.discussion_run
        if discussion is not None:
            assert discussion.run_id.startswith(prefix)
            assert all(
                message.run_id == discussion.run_id
                for message in discussion.messages
            )
            assert all(
                message.message_id.startswith(prefix)
                for message in discussion.messages
            )
    if session.final_theory is not None:
        assert session.final_theory.final_theory_id.startswith(prefix)
        assert all(
            item.startswith(prefix) for item in session.final_theory.hypothesis_ids
        )
        assert all(
            item.clue_id.startswith(prefix) for item in session.final_theory.evidence
        )
    serialized = session.model_dump_json()
    assert prefix in serialized
    assert f"{other}_" not in serialized


def test_complete_single_session_workflow_through_real_http(
    http_workflow: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, output_root = http_workflow
    assert "OPENAI_API_KEY" not in os.environ
    initial_files = output_files(output_root)
    introduction = "A curator vanished from the sealed map archive."
    clue_one = "A brass key lay beside the locked inner door."
    clue_two = "Fresh mud stopped at the corridor entrance."

    post_prg(
        client,
        "session_001",
        data={"characters": CHARACTERS, "introduction": introduction},
    )
    assert registry.session_ids == ("session_001",)
    created = registry.get("session_001")
    assert created.session.status is InvestigationStatus.ACTIVE
    assert created.session.case_introduction == introduction
    assert created.session.clues == created.session.rounds == ()
    assert created.session.analyses == created.session.decisions == ()
    assert created.session.final_theory is None
    page = get_without_mutation(client, registry, "session_001")
    assert "Waiting for the Game Master to reveal the first clue." in page
    assert "/session_001/clues" in page
    for suffix in ("analyses", "discussion", "decision", "finalize"):
        assert f"/session_001/{suffix}" not in page

    post_prg(client, "session_001", "clues", data={"clue": clue_one})
    revealed_one = registry.get("session_001")
    assert len(revealed_one.session.clues) == len(revealed_one.session.rounds) == 1
    round_one = revealed_one.session.rounds[0]
    clue_one_id = revealed_one.session.clues[0].clue_id
    assert round_one.status is InvestigationRoundStatus.AWAITING_ANALYSES
    assert round_one.visible_clue_ids == (clue_one_id,)
    page = get_without_mutation(client, registry, "session_001")
    assert clue_one in page and "Run independent analyses" in page
    assert "Run group discussion" not in page
    assert "Create group decision" not in page
    assert "Finalize investigation" not in page
    assert get_without_mutation(client, registry, "session_001") == page

    post_prg(client, "session_001", "analyses")
    analysed_one = registry.get("session_001")
    round_one = analysed_one.session.rounds[0]
    analyses_one = round_analyses(analysed_one.session, round_one.round_id)
    assert round_one.status is InvestigationRoundStatus.AWAITING_DISCUSSION
    assert tuple(item.agent_id for item in analyses_one) == (
        analysed_one.session.participant_ids
    )
    assert all(item.session_id == "session_001" for item in analyses_one)
    assert all(item.round_id == round_one.round_id for item in analyses_one)
    assert all(item.visible_clue_ids == (clue_one_id,) for item in analyses_one)
    page = get_without_mutation(client, registry, "session_001")
    assert "SHERLOCK_R1" in page and "POIROT_R1" in page
    assert "Run group discussion" in page and "Run independent analyses" not in page

    post_prg(client, "session_001", "discussion")
    discussed_one = registry.get("session_001")
    assert discussed_one.session.rounds[0].status is (
        InvestigationRoundStatus.AWAITING_DECISION
    )
    assert_discussion_order(discussed_one, 0)
    page = get_without_mutation(client, registry, "session_001")
    assert "Round 1 discussion" in page and "Create group decision" in page
    assert "Run group discussion" not in page

    post_prg(client, "session_001", "decision")
    paused_one = registry.get("session_001")
    assert paused_one.session.status is InvestigationStatus.ACTIVE
    assert paused_one.session.rounds[0].status is InvestigationRoundStatus.COMPLETED
    assert len(paused_one.session.decisions) == 1
    assert paused_one.session.decisions[0].round_id == (
        paused_one.session.rounds[0].round_id
    )
    assert len(paused_one.session.clues) == len(paused_one.session.rounds) == 1
    page = get_without_mutation(client, registry, "session_001")
    assert "Round 1 group decision" in page
    assert "Waiting for the Game Master to reveal the next clue." in page
    assert "/session_001/clues" in page and "Finalize investigation" not in page
    assert registry.get("session_001") is paused_one

    frozen_round_one = paused_one.session.rounds[0]
    frozen_analyses_one = analyses_one
    frozen_discussion_one = frozen_round_one.discussion_run
    post_prg(client, "session_001", "clues", data={"clue": clue_two})
    revealed_two = registry.get("session_001")
    assert len(revealed_two.session.clues) == len(revealed_two.session.rounds) == 2
    clue_two_id = revealed_two.session.clues[1].clue_id
    assert revealed_two.session.rounds[0] == frozen_round_one
    assert revealed_two.session.rounds[0].visible_clue_ids == (clue_one_id,)
    assert revealed_two.session.rounds[1].visible_clue_ids == (clue_one_id, clue_two_id)
    assert revealed_two.session.rounds[1].status is (
        InvestigationRoundStatus.AWAITING_ANALYSES
    )

    post_prg(client, "session_001", "analyses")
    analysed_two = registry.get("session_001")
    round_two = analysed_two.session.rounds[1]
    analyses_two = round_analyses(analysed_two.session, round_two.round_id)
    assert round_two.status is InvestigationRoundStatus.AWAITING_DISCUSSION
    assert round_analyses(
        analysed_two.session,
        frozen_round_one.round_id,
    ) == frozen_analyses_one
    assert tuple(item.agent_id for item in analyses_two) == (
        analysed_two.session.participant_ids
    )
    assert all(item.session_id == "session_001" for item in analyses_two)
    assert all(
        item.visible_clue_ids == (clue_one_id, clue_two_id)
        for item in analyses_two
    )
    page = get_without_mutation(client, registry, "session_001")
    assert "Round 1 analyses" in page and "Round 2 analyses" in page

    post_prg(client, "session_001", "discussion")
    discussed_two = registry.get("session_001")
    assert discussed_two.session.rounds[0].discussion_run == frozen_discussion_one
    assert discussed_two.session.rounds[1].status is (
        InvestigationRoundStatus.AWAITING_DECISION
    )
    assert_discussion_order(discussed_two, 1)
    page = get_without_mutation(client, registry, "session_001")
    assert "Round 1 discussion" in page and "Round 2 discussion" in page

    post_prg(client, "session_001", "decision")
    exhausted = registry.get("session_001")
    assert exhausted.session.status is InvestigationStatus.ACTIVE
    assert exhausted.session.rounds[1].status is InvestigationRoundStatus.COMPLETED
    assert len(exhausted.session.decisions) == 2
    assert exhausted.session.final_theory is None
    page = get_without_mutation(client, registry, "session_001")
    assert "no more clue rounds available" in page
    assert "Finalize investigation" in page
    assert "/session_001/clues" not in page
    assert 'id="final-theory-title"' not in page
    assert registry.get("session_001") is exhausted

    conflict = client.post(
        "/investigations/session_001/clues",
        data={"clue": "A third clue must be rejected."},
    )
    assert conflict.status_code == 409
    assert registry.get("session_001") is exhausted
    assert len(exhausted.session.clues) == len(exhausted.session.rounds) == 2
    assert exhausted.session.final_theory is None

    post_prg(client, "session_001", "finalize")
    completed = registry.get("session_001")
    assert completed.session.status is InvestigationStatus.COMPLETED
    assert completed.session.final_theory is not None
    assert completed.session.final_theory.final_theory_id.startswith("session_001_")
    assert len(completed.session.clues) == len(completed.session.rounds) == 2
    assert len(completed.session.analyses) == 2 * len(completed.session.participant_ids)
    assert len(completed.session.decisions) == 2
    assert all(item.discussion_run is not None for item in completed.session.rounds)
    page = get_without_mutation(client, registry, "session_001")
    assert "This investigation is completed." in page and "Final theory" in page
    for heading in (
        "Round 1 analyses", "Round 1 discussion", "Round 1 group decision",
        "Round 2 analyses", "Round 2 discussion", "Round 2 group decision",
    ):
        assert heading in page
    for action in (
        "Reveal clue", "Run independent analyses", "Run group discussion",
        "Create group decision", "Finalize investigation",
    ):
        assert action not in page
    for _ in range(2):
        get_without_mutation(client, registry, "session_001")
    assert registry.get("session_001") is completed
    assert output_files(output_root) == initial_files == ()


def test_two_sessions_progress_interleaved_without_namespace_leaks(
    http_workflow: tuple[
        ASGITestClient,
        InMemoryInvestigationRegistry,
        Path,
    ],
) -> None:
    client, registry, output_root = http_workflow
    initial_files = output_files(output_root)
    introductions = {
        "session_001": "The observatory log vanished during the eclipse.",
        "session_002": "A violin disappeared from the sealed recital room.",
    }
    clues = {
        "session_001": (
            "Blue chalk marked the telescope.",
            "The dome latch was oiled.",
        ),
        "session_002": (
            "A snapped string lay by the case.",
            "Wax marked the service door.",
        ),
    }

    for session_id in ("session_001", "session_002"):
        post_prg(
            client,
            session_id,
            data={"characters": CHARACTERS, "introduction": introductions[session_id]},
        )
    assert registry.session_ids == ("session_001", "session_002")

    def act(
        session_id: str,
        suffix: str,
        *,
        data: dict[str, str] | None = None,
    ) -> None:
        other = "session_002" if session_id == "session_001" else "session_001"
        other_before = registry.get(other)
        post_prg(client, session_id, suffix, data=data)
        assert registry.get(other) is other_before
        assert registry.get(other).session.case_introduction == introductions[other]
        assert all(
            clue.text in clues[other]
            for clue in registry.get(other).session.clues
        )

    act("session_001", "clues", data={"clue": clues["session_001"][0]})
    first_after_clue = registry.get("session_001")
    act("session_002", "clues", data={"clue": clues["session_002"][0]})
    assert registry.get("session_001") is first_after_clue
    act("session_002", "analyses")
    act("session_001", "analyses")
    assert_structural_namespace(
        registry.get("session_001").session,
        "session_001",
        "session_002",
    )
    assert_structural_namespace(
        registry.get("session_002").session,
        "session_002",
        "session_001",
    )
    act("session_001", "discussion")
    act("session_002", "discussion")
    assert_discussion_order(registry.get("session_001"), 0)
    assert_discussion_order(registry.get("session_002"), 0)
    act("session_002", "decision")
    act("session_001", "decision")
    assert all(len(registry.get(item).session.rounds) == 1 for item in introductions)

    act("session_001", "clues", data={"clue": clues["session_001"][1]})
    act("session_002", "clues", data={"clue": clues["session_002"][1]})
    act("session_002", "analyses")
    act("session_001", "analyses")
    assert_structural_namespace(
        registry.get("session_001").session,
        "session_001",
        "session_002",
    )
    assert_structural_namespace(
        registry.get("session_002").session,
        "session_002",
        "session_001",
    )
    act("session_001", "discussion")
    act("session_002", "discussion")
    assert_discussion_order(registry.get("session_001"), 1)
    assert_discussion_order(registry.get("session_002"), 1)
    act("session_002", "decision")
    act("session_001", "decision")

    second_before_first_finalization = registry.get("session_002")
    act("session_001", "finalize")
    assert registry.get("session_002") is second_before_first_finalization
    assert registry.get("session_001").session.status is InvestigationStatus.COMPLETED
    assert registry.get("session_002").session.status is InvestigationStatus.ACTIVE
    act("session_002", "finalize")

    first = registry.get("session_001")
    second = registry.get("session_002")
    assert first.session.status is second.session.status is (
        InvestigationStatus.COMPLETED
    )
    assert first.session.final_theory is not None
    assert second.session.final_theory is not None
    assert first.session.final_theory.final_theory_id != (
        second.session.final_theory.final_theory_id
    )
    assert len(first.session.rounds) == len(second.session.rounds) == 2
    assert len(first.session.decisions) == len(second.session.decisions) == 2
    assert tuple(item.text for item in first.session.clues) == clues["session_001"]
    assert tuple(item.text for item in second.session.clues) == clues["session_002"]
    assert first.session.case_introduction == introductions["session_001"]
    assert second.session.case_introduction == introductions["session_002"]
    assert_structural_namespace(first.session, "session_001", "session_002")
    assert_structural_namespace(second.session, "session_002", "session_001")
    assert get_without_mutation(client, registry, "session_001")
    assert get_without_mutation(client, registry, "session_002")
    assert output_files(output_root) == initial_files == ()
