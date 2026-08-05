"""Standalone contracts for selecting one conversation participant.

Selectors receive ordered, unique participant identifiers, read-only message
history, and an explicit zero-based turn index. They return a participant
identifier and own no generation, prompt, provider, persistence, or history
state. Duplicate identifiers are rejected rather than silently normalized.
"""

from collections.abc import Sequence
from typing import Protocol

from multi_agent_personalities.models.message import Message


class SpeakerSelector(Protocol):
    """Structural interface for choosing the next participant identifier."""

    def select_next(
        self,
        *,
        participant_ids: Sequence[str],
        history: Sequence[Message],
        turn_index: int,
    ) -> str:
        """Return the stable identifier of the selected participant."""
        ...


class RoundRobinSelector:
    """Select by configured order and explicit turn index without state."""

    def select_next(
        self,
        *,
        participant_ids: Sequence[str],
        history: Sequence[Message],
        turn_index: int,
    ) -> str:
        """Return ``participant_ids[turn_index % len(participant_ids)]``."""

        del history  # Round-robin intentionally ignores message content.
        _validate_selection_inputs(participant_ids, turn_index)
        return participant_ids[turn_index % len(participant_ids)]


def select_valid_speaker(
    selector: SpeakerSelector,
    *,
    participant_ids: Sequence[str],
    history: Sequence[Message],
    turn_index: int,
) -> str:
    """Invoke a selector and require a supplied participant identifier."""

    _validate_selection_inputs(participant_ids, turn_index)
    selected_character_id = selector.select_next(
        participant_ids=participant_ids,
        history=history,
        turn_index=turn_index,
    )
    if selected_character_id not in participant_ids:
        raise ValueError(
            "speaker selector returned unsupported participant identifier: "
            f"{selected_character_id!r}"
        )
    return selected_character_id


def _validate_selection_inputs(
    participant_ids: Sequence[str],
    turn_index: int,
) -> None:
    if isinstance(participant_ids, (str, bytes)):
        raise ValueError("participant_ids must be a sequence of identifiers")
    if not participant_ids:
        raise ValueError("at least one participant identifier is required")
    if any(
        not isinstance(participant_id, str) or not participant_id.strip()
        for participant_id in participant_ids
    ):
        raise ValueError("participant identifiers must be non-empty strings")
    if len(participant_ids) != len(set(participant_ids)):
        raise ValueError("participant identifiers must not contain duplicates")
    if isinstance(turn_index, bool) or not isinstance(turn_index, int):
        raise ValueError("turn_index must be a non-negative integer")
    if turn_index < 0:
        raise ValueError("turn_index must be greater than or equal to zero")
