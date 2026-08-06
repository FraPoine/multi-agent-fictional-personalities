"""Generic reply-generation contract for one simulation turn."""

from datetime import datetime
from typing import Protocol

from multi_agent_personalities.models import Message
from multi_agent_personalities.simulation.participant import (
    ConversationParticipant,
)


class TurnReplyGenerator(Protocol):
    """Generate one message for an engine-selected participant and turn."""

    def __call__(
        self,
        *,
        participant: ConversationParticipant,
        history: tuple[Message, ...],
        topic: str,
        run_id: str,
        turn_index: int,
        timestamp: datetime,
    ) -> Message:
        """Return one validated message without controlling loop structure."""
        ...
