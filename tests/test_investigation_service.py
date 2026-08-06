"""Tests for stateless investigation session and clue-reveal operations."""

import inspect
import socket

import pytest
from pydantic import ValidationError

from multi_agent_personalities.application import create_session, reveal_clue
from multi_agent_personalities.models import (
    GroupDecision,
    GroupDecisionType,
    InvestigationRound,
    InvestigationRoundStatus,
    InvestigationSession,
    InvestigationStatus,
)


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)


def new_session(**overrides: object) -> InvestigationSession:
    arguments: dict[str, object] = {
        "session_id": "session_001",
        "introduction": "  A visitor vanished from a locked room.  ",
        "participant_ids": ("sherlock", "poirot"),
    }
    arguments.update(overrides)
    return create_session(**arguments)  # type: ignore[arg-type]


def complete_current_round(session: InvestigationSession) -> InvestigationSession:
    investigation_round = session.rounds[-1]
    decision = GroupDecision(
        decision_id=f"{investigation_round.round_id}_decision",
        session_id=session.session_id,
        round_id=investigation_round.round_id,
        decision_type=GroupDecisionType.REQUEST_INFORMATION,
        summary="Request the next clue.",
    )
    payload = session.model_dump(mode="python")
    rounds = list(payload["rounds"])
    rounds[-1] = {
        **rounds[-1],
        "decision_id": decision.decision_id,
        "status": InvestigationRoundStatus.COMPLETED,
    }
    payload["rounds"] = rounds
    payload["decisions"] = (*session.decisions, decision)
    return InvestigationSession.model_validate(payload)


def test_create_session_returns_empty_active_immutable_aggregate() -> None:
    session = new_session()

    assert session.status is InvestigationStatus.ACTIVE
    assert session.session_id == "session_001"
    assert session.case_introduction == "  A visitor vanished from a locked room.  "
    assert session.participant_ids == ("sherlock", "poirot")
    assert session.clues == ()
    assert session.rounds == ()
    assert session.analyses == ()
    assert session.hypotheses == ()
    assert session.decisions == ()
    assert session.final_theory is None
    with pytest.raises(ValidationError):
        session.status = InvestigationStatus.COMPLETED


def test_create_session_supports_more_than_two_ordered_participants() -> None:
    participants = ["poirot", "sherlock", "layton"]
    original = list(participants)

    session = new_session(participant_ids=participants)

    assert session.participant_ids == tuple(original)
    assert participants == original


@pytest.mark.parametrize(
    ("participants", "message"),
    [
        (("sherlock",), "at least 2"),
        (("sherlock", "sherlock"), "duplicates"),
        (("sherlock", ""), "string"),
    ],
)
def test_create_session_rejects_invalid_participants(
    participants: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises((ValueError, ValidationError), match=message):
        new_session(participant_ids=participants)


@pytest.mark.parametrize("introduction", ["", " \t\n"])
def test_create_session_rejects_blank_introduction(introduction: str) -> None:
    with pytest.raises(ValueError, match="introduction"):
        new_session(introduction=introduction)


@pytest.mark.parametrize(
    "session_id",
    ["", "   ", "../session", "session/001", "_session", 1],
)
def test_create_session_rejects_invalid_session_id(session_id: object) -> None:
    with pytest.raises(ValueError, match="run_id"):
        new_session(session_id=session_id)


def test_repeated_session_creation_is_equivalent() -> None:
    assert new_session() == new_session()


def test_first_reveal_adds_exactly_one_clue_and_round() -> None:
    original = new_session()

    updated = reveal_clue(original, clue_text="  The window is open.  ")

    assert updated.status is InvestigationStatus.ACTIVE
    assert len(updated.clues) == 1
    assert updated.clues[0].clue_id == "session_001_clue_0001"
    assert updated.clues[0].text == "  The window is open.  "
    assert updated.clues[0].reveal_order == 0
    assert len(updated.rounds) == 1
    investigation_round = updated.rounds[0]
    assert investigation_round.session_id == original.session_id
    assert investigation_round.round_id == "session_001_round_0001"
    assert investigation_round.round_index == 1
    assert investigation_round.revealed_clue_id == updated.clues[0].clue_id
    assert investigation_round.visible_clue_ids == (updated.clues[0].clue_id,)
    assert investigation_round.analysis_ids == ()
    assert investigation_round.discussion_run is None
    assert investigation_round.decision_id is None
    assert investigation_round.status is InvestigationRoundStatus.AWAITING_ANALYSES
    assert original.clues == ()
    assert original.rounds == ()


def test_revealed_session_json_round_trip_preserves_order() -> None:
    updated = reveal_clue(new_session(), clue_text="The window is open.")

    restored = InvestigationSession.model_validate_json(updated.model_dump_json())

    assert restored == updated
    assert restored.clues[0].clue_id == "session_001_clue_0001"
    assert restored.rounds[0].visible_clue_ids == (
        "session_001_clue_0001",
    )


def test_generated_ids_are_deterministic_and_one_based() -> None:
    first = reveal_clue(new_session(), clue_text="First clue.")
    second = reveal_clue(new_session(), clue_text="First clue.")

    assert first.clues[0].clue_id == second.clues[0].clue_id
    assert first.rounds[0].round_id == second.rounds[0].round_id
    assert first.clues[0].clue_id.endswith("clue_0001")
    assert first.rounds[0].round_id.endswith("round_0001")
    assert "-" not in first.clues[0].clue_id


def test_explicit_valid_clue_id_is_preserved() -> None:
    updated = reveal_clue(
        new_session(),
        clue_text="First clue.",
        clue_id="game_master_clue_A",
    )

    assert updated.clues[0].clue_id == "game_master_clue_A"
    assert updated.rounds[0].revealed_clue_id == "game_master_clue_A"


@pytest.mark.parametrize("clue_id", ["", " ", "../clue", "clue/001", "_clue"])
def test_invalid_explicit_clue_id_is_rejected(clue_id: str) -> None:
    with pytest.raises(ValueError, match="run_id"):
        reveal_clue(new_session(), clue_text="A clue.", clue_id=clue_id)


def test_duplicate_explicit_clue_id_is_rejected_without_replacement() -> None:
    first = reveal_clue(
        new_session(), clue_text="First.", clue_id="explicit_clue"
    )
    completed = complete_current_round(first)
    before = completed.model_dump_json()

    with pytest.raises(ValueError, match="duplicate clue_id"):
        reveal_clue(
            completed,
            clue_text="Second.",
            clue_id="explicit_clue",
        )

    assert completed.model_dump_json() == before
    assert tuple(item.clue_id for item in completed.clues) == ("explicit_clue",)


def test_second_reveal_preserves_history_and_extends_visibility() -> None:
    first = reveal_clue(new_session(), clue_text="First clue.")
    completed = complete_current_round(first)
    prior_round_json = completed.rounds[0].model_dump_json()

    updated = reveal_clue(completed, clue_text="Second clue.")

    assert updated.status is InvestigationStatus.ACTIVE
    assert tuple(item.reveal_order for item in updated.clues) == (0, 1)
    assert tuple(item.clue_id for item in updated.clues) == (
        "session_001_clue_0001",
        "session_001_clue_0002",
    )
    assert tuple(item.round_index for item in updated.rounds) == (1, 2)
    assert updated.rounds[1].round_id == "session_001_round_0002"
    assert updated.rounds[1].visible_clue_ids == (
        "session_001_clue_0001",
        "session_001_clue_0002",
    )
    assert updated.rounds[0].model_dump_json() == prior_round_json


@pytest.mark.parametrize(
    "status",
    [
        InvestigationRoundStatus.AWAITING_ANALYSES,
        InvestigationRoundStatus.AWAITING_DISCUSSION,
        InvestigationRoundStatus.AWAITING_DECISION,
    ],
)
def test_incomplete_round_blocks_another_reveal(
    status: InvestigationRoundStatus,
) -> None:
    first = reveal_clue(new_session(), clue_text="First clue.")
    payload = first.model_dump(mode="python")
    payload["rounds"][0]["status"] = status
    incomplete = InvestigationSession.model_validate(payload)
    before = incomplete.model_dump_json()

    with pytest.raises(ValueError, match="current round is incomplete"):
        reveal_clue(incomplete, clue_text="Second clue.")

    assert incomplete.model_dump_json() == before
    assert len(incomplete.clues) == 1
    assert len(incomplete.rounds) == 1


def test_completed_session_rejects_reveal() -> None:
    payload = new_session().model_dump(mode="python")
    payload["status"] = InvestigationStatus.COMPLETED
    payload["final_theory"] = {"final_theory_id": "final", "summary": "Done."}
    completed = InvestigationSession.model_validate(payload)

    with pytest.raises(ValueError, match="only in an active session"):
        reveal_clue(completed, clue_text="Too late.")


@pytest.mark.parametrize(
    "status",
    [
        InvestigationStatus.SETUP,
        InvestigationStatus.READY_FOR_FINAL,
        InvestigationStatus.ABANDONED,
    ],
)
def test_non_operational_session_status_rejects_reveal(
    status: InvestigationStatus,
) -> None:
    payload = new_session().model_dump(mode="python")
    payload["status"] = status
    session = InvestigationSession.model_validate(payload)

    with pytest.raises(ValueError, match="only in an active session"):
        reveal_clue(session, clue_text="A clue.")


@pytest.mark.parametrize("clue_text", ["", " \t\n"])
def test_reveal_rejects_blank_clue_text(clue_text: str) -> None:
    with pytest.raises(ValueError, match="clue_text"):
        reveal_clue(new_session(), clue_text=clue_text)


def test_inconsistent_input_snapshot_is_not_repaired() -> None:
    invalid_round = InvestigationRound.model_construct(
        session_id="session_001",
        round_id="session_001_round_0002",
        round_index=2,
        revealed_clue_id="session_001_clue_0001",
        visible_clue_ids=("session_001_clue_0001",),
        analysis_ids=(),
        discussion_run=None,
        decision_id=None,
        status=InvestigationRoundStatus.AWAITING_ANALYSES,
    )
    invalid_session = InvestigationSession.model_construct(
        session_id="session_001",
        case_introduction="A case.",
        participant_ids=("sherlock", "poirot"),
        status=InvestigationStatus.ACTIVE,
        clues=(),
        rounds=(invalid_round,),
        analyses=(),
        hypotheses=(),
        decisions=(),
        final_theory=None,
    )

    with pytest.raises(ValidationError, match="round_index"):
        reveal_clue(invalid_session, clue_text="A clue.")


def test_service_has_no_provider_dependency() -> None:
    assert "provider" not in inspect.signature(create_session).parameters
    assert "provider" not in inspect.signature(reveal_clue).parameters
    assert reveal_clue(new_session(), clue_text="A clue.").clues
