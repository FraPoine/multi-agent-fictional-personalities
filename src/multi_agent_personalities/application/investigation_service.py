"""Stateless application operations for deterministic investigation setup."""

from collections.abc import Sequence

from multi_agent_personalities.application.investigation_ids import (
    DeterministicInvestigationIdFactory,
)
from multi_agent_personalities.models import (
    Clue,
    InvestigationRound,
    InvestigationRoundStatus,
    InvestigationSession,
    InvestigationStatus,
)


def create_session(
    *,
    id_factory: DeterministicInvestigationIdFactory,
    introduction: str,
    participant_ids: Sequence[str],
) -> InvestigationSession:
    """Create one validated active investigation with no revealed state."""
    if not isinstance(id_factory, DeterministicInvestigationIdFactory):
        raise ValueError(
            "id_factory must be a DeterministicInvestigationIdFactory"
        )
    session_id = id_factory.session_id
    id_factory.clue_id(0)
    id_factory.round_id(1)
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
    id_factory: DeterministicInvestigationIdFactory,
) -> InvestigationSession:
    """Reveal exactly one caller-supplied clue and open its analysis round."""
    if not isinstance(session, InvestigationSession):
        raise ValueError("session must be a validated InvestigationSession")
    session = InvestigationSession.model_validate(
        session.model_dump(mode="python")
    )
    if not isinstance(id_factory, DeterministicInvestigationIdFactory):
        raise ValueError(
            "id_factory must be a DeterministicInvestigationIdFactory"
        )
    if id_factory.session_id != session.session_id:
        raise ValueError("id_factory session_id must match the investigation session")
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
    if any(
        item.status is not InvestigationRoundStatus.COMPLETED
        for item in session.rounds
    ):
        raise ValueError("cannot reveal a clue while any existing round is incomplete")
    if not isinstance(clue_text, str) or not clue_text.strip():
        raise ValueError("clue_text must not be empty")

    reveal_order = len(session.clues)
    resolved_clue_id = id_factory.clue_id(reveal_order)
    if any(item.clue_id == resolved_clue_id for item in session.clues):
        raise ValueError(f"duplicate clue_id: {resolved_clue_id!r}")

    round_index = len(session.rounds) + 1
    resolved_round_id = id_factory.round_id(round_index)
    if any(item.round_id == resolved_round_id for item in session.rounds):
        raise ValueError(f"duplicate round_id: {resolved_round_id!r}")
    new_clue = Clue(
        clue_id=resolved_clue_id,
        text=clue_text,
        reveal_order=reveal_order,
    )
    updated_clues = (*session.clues, new_clue)
    new_round = InvestigationRound(
        session_id=session.session_id,
        round_id=resolved_round_id,
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
