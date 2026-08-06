"""Tests for stateless investigation session and clue-reveal operations."""

import inspect
import socket

import pytest
from pydantic import ValidationError

from multi_agent_personalities.application import (
    DeterministicInvestigationIdFactory,
    create_session,
    reveal_clue,
)
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
        "id_factory": DeterministicInvestigationIdFactory(1),
        "introduction": "  A visitor vanished from a locked room.  ",
        "participant_ids": ("sherlock", "poirot"),
    }
    arguments.update(overrides)
    return create_session(**arguments)  # type: ignore[arg-type]


def reveal(
    session: InvestigationSession,
    clue_text: str,
    *,
    id_factory: DeterministicInvestigationIdFactory | None = None,
) -> InvestigationSession:
    return reveal_clue(
        session,
        clue_text=clue_text,
        id_factory=id_factory or DeterministicInvestigationIdFactory(1),
    )


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
    analysis_ids = tuple(
        f"{investigation_round.round_id}_{participant}_analysis"
        for participant in session.participant_ids
    )
    payload["analyses"] = (*payload["analyses"], *(
        {
            "analysis_id": analysis_id,
            "session_id": session.session_id,
            "round_id": investigation_round.round_id,
            "agent_id": participant,
            "visible_clue_ids": investigation_round.visible_clue_ids,
            "facts": ("A fact.",),
        }
        for analysis_id, participant in zip(analysis_ids, session.participant_ids)
    ))
    discussion_id = f"{investigation_round.round_id}_discussion"
    discussion = {
        "run_id": discussion_id,
        "topic": "Case discussion.",
        "character_ids": session.participant_ids,
        "turn_count": 2,
        "seed": 42,
        "provider": "mock",
        "created_at": "2026-08-06T12:00:00Z",
        "status": "completed",
        "messages": tuple(
            {
                "message_id": f"{discussion_id}_message_{index + 1}",
                "run_id": discussion_id,
                "turn_index": index,
                "speaker_character_id": participant,
                "speaker_name": participant.title(),
                "text": "A point.",
                "provider": "mock",
                "timestamp": "2026-08-06T12:00:00Z",
            }
            for index, participant in enumerate(session.participant_ids)
        ),
    }
    rounds = list(payload["rounds"])
    rounds[-1] = {
        **rounds[-1],
        "analysis_ids": analysis_ids,
        "discussion_run": discussion,
        "decision_id": decision.decision_id,
        "status": InvestigationRoundStatus.COMPLETED,
    }
    payload["rounds"] = rounds
    payload["decisions"] = (*session.decisions, decision.model_copy(update={"analysis_ids": analysis_ids}))
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


def test_repeated_session_creation_is_equivalent() -> None:
    assert new_session() == new_session()


def test_first_reveal_adds_exactly_one_clue_and_round() -> None:
    original = new_session()

    updated = reveal(original, "  The window is open.  ")

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
    updated = reveal(new_session(), "The window is open.")

    restored = InvestigationSession.model_validate_json(updated.model_dump_json())

    assert restored == updated
    assert restored.clues[0].clue_id == "session_001_clue_0001"
    assert restored.rounds[0].visible_clue_ids == (
        "session_001_clue_0001",
    )


def test_generated_ids_are_deterministic_and_one_based() -> None:
    first = reveal(new_session(), "First clue.")
    second = reveal(new_session(), "First clue.")

    assert first.clues[0].clue_id == second.clues[0].clue_id
    assert first.rounds[0].round_id == second.rounds[0].round_id
    assert first.clues[0].clue_id.endswith("clue_0001")
    assert first.rounds[0].round_id.endswith("round_0001")
    assert "-" not in first.clues[0].clue_id


def test_service_does_not_accept_caller_owned_session_or_clue_ids() -> None:
    assert "session_id" not in inspect.signature(create_session).parameters
    assert "clue_id" not in inspect.signature(reveal_clue).parameters


def test_second_reveal_preserves_history_and_extends_visibility() -> None:
    first = reveal(new_session(), "First clue.")
    completed = complete_current_round(first)
    prior_round_json = completed.rounds[0].model_dump_json()

    updated = reveal(completed, "Second clue.")

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


def test_reveal_rejects_factory_for_another_session() -> None:
    session = new_session()

    with pytest.raises(ValueError, match="session_id must match"):
        reveal(
            session,
            "A clue.",
            id_factory=DeterministicInvestigationIdFactory(2),
        )


def test_any_incomplete_historical_round_blocks_reveal() -> None:
    first = complete_current_round(reveal(new_session(), "First clue."))
    second = complete_current_round(reveal(first, "Second clue."))
    payload = second.model_dump(mode="python")
    payload["rounds"][0]["decision_id"] = None
    payload["rounds"][0]["status"] = "awaiting_decision"
    payload["decisions"] = payload["decisions"][1:]
    inconsistent_progress = InvestigationSession.model_validate(payload)

    with pytest.raises(ValueError, match="any existing round is incomplete"):
        reveal(inconsistent_progress, "Third clue.")


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
    first = reveal(new_session(), "First clue.")
    if status is InvestigationRoundStatus.AWAITING_ANALYSES:
        payload = first.model_dump(mode="python")
    else:
        payload = complete_current_round(first).model_dump(mode="python")
        payload["rounds"][0]["decision_id"] = None
        payload["decisions"] = ()
        if status is InvestigationRoundStatus.AWAITING_DISCUSSION:
            payload["rounds"][0]["discussion_run"] = None
    payload["rounds"][0]["status"] = status
    incomplete = InvestigationSession.model_validate(payload)
    before = incomplete.model_dump_json()

    with pytest.raises(ValueError, match="any existing round is incomplete"):
        reveal(incomplete, "Second clue.")

    assert incomplete.model_dump_json() == before
    assert len(incomplete.clues) == 1
    assert len(incomplete.rounds) == 1


def test_completed_session_rejects_reveal() -> None:
    payload = new_session().model_dump(mode="python")
    payload["status"] = InvestigationStatus.COMPLETED
    payload["final_theory"] = {"final_theory_id": "final", "summary": "Done."}
    completed = InvestigationSession.model_validate(payload)

    with pytest.raises(ValueError, match="only in an active session"):
        reveal(completed, "Too late.")


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
        reveal(session, "A clue.")


@pytest.mark.parametrize("clue_text", ["", " \t\n"])
def test_reveal_rejects_blank_clue_text(clue_text: str) -> None:
    with pytest.raises(ValueError, match="clue_text"):
        reveal(new_session(), clue_text)


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
        reveal(invalid_session, "A clue.")


def test_service_has_no_provider_dependency() -> None:
    assert "provider" not in inspect.signature(create_session).parameters
    assert "provider" not in inspect.signature(reveal_clue).parameters
    assert reveal(new_session(), "A clue.").clues
