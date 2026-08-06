"""Stateless application operations for deterministic investigation setup."""

from collections.abc import Sequence

from multi_agent_personalities.models import (
    Clue,
    InvestigationRound,
    InvestigationRoundStatus,
    InvestigationSession,
    InvestigationStatus,
    validate_run_id,
)


def _build_clue_id(session_id: str, reveal_order: int) -> str:
    """Return the one-based deterministic clue ID for a reveal position."""
    return validate_run_id(f"{session_id}_clue_{reveal_order + 1:04d}")


def _build_round_id(session_id: str, round_index: int) -> str:
    """Return the deterministic round ID for a one-based round index."""
    return validate_run_id(f"{session_id}_round_{round_index:04d}")


def create_session(
    *,
    session_id: str,
    introduction: str,
    participant_ids: Sequence[str],
) -> InvestigationSession:
    """Create one validated active investigation with no revealed state."""
    validate_run_id(session_id)
    if not isinstance(introduction, str) or not introduction.strip():
        raise ValueError("introduction must not be empty")
    if isinstance(participant_ids, (str, bytes)) or not isinstance(
        participant_ids, Sequence
    ):
        raise ValueError("participant_ids must be a sequence of identifiers")

    return InvestigationSession(
        session_id=session_id,
        case_introduction=introduction,
        participant_ids=tuple(participant_ids),
        status=InvestigationStatus.ACTIVE,
    )


def reveal_clue(
    session: InvestigationSession,
    *,
    clue_text: str,
    clue_id: str | None = None,
) -> InvestigationSession:
    """Reveal exactly one caller-supplied clue and open its analysis round."""
    if not isinstance(session, InvestigationSession):
        raise ValueError("session must be a validated InvestigationSession")
    session = InvestigationSession.model_validate(
        session.model_dump(mode="python")
    )
    if session.status is not InvestigationStatus.ACTIVE:
        raise ValueError("clues may be revealed only in an active session")
    if len(session.clues) != len(session.rounds):
        raise ValueError("session clue and round history is inconsistent")
    for index, investigation_round in enumerate(session.rounds):
        expected_visible_ids = tuple(
            item.clue_id for item in session.clues[: index + 1]
        )
        if (
            investigation_round.revealed_clue_id
            != session.clues[index].clue_id
            or investigation_round.visible_clue_ids != expected_visible_ids
        ):
            raise ValueError("session clue and round history is inconsistent")
    if session.rounds and (
        session.rounds[-1].status is not InvestigationRoundStatus.COMPLETED
    ):
        raise ValueError("cannot reveal a clue while the current round is incomplete")
    if not isinstance(clue_text, str) or not clue_text.strip():
        raise ValueError("clue_text must not be empty")

    reveal_order = len(session.clues)
    resolved_clue_id = (
        _build_clue_id(session.session_id, reveal_order)
        if clue_id is None
        else validate_run_id(clue_id)
    )
    if any(item.clue_id == resolved_clue_id for item in session.clues):
        raise ValueError(f"duplicate clue_id: {resolved_clue_id!r}")

    round_index = len(session.rounds) + 1
    new_clue = Clue(
        clue_id=resolved_clue_id,
        text=clue_text,
        reveal_order=reveal_order,
    )
    updated_clues = (*session.clues, new_clue)
    new_round = InvestigationRound(
        session_id=session.session_id,
        round_id=_build_round_id(session.session_id, round_index),
        round_index=round_index,
        revealed_clue_id=resolved_clue_id,
        visible_clue_ids=tuple(item.clue_id for item in updated_clues),
        status=InvestigationRoundStatus.AWAITING_ANALYSES,
    )

    payload = session.model_dump(mode="python")
    payload.update(
        status=InvestigationStatus.ACTIVE,
        clues=updated_clues,
        rounds=(*session.rounds, new_round),
    )
    return InvestigationSession.model_validate(payload)
