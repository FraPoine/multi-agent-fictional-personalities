"""Immutable runtime binding between persona identity and generation provider."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from multi_agent_personalities.agent_runtime import generate_reply
from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.models import Message, Persona


@dataclass(frozen=True)
class ConversationParticipant:
    """Bind one persona to its provider and declared run-level metadata."""

    persona: Persona
    provider: LLMProvider
    provider_name: str
    model_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise ValueError("provider_name must not be empty")
        if self.model_name is not None and (
            not isinstance(self.model_name, str) or not self.model_name.strip()
        ):
            raise ValueError("model_name must not be empty when provided")

    @property
    def character_id(self) -> str:
        """Return the stable identity owned by the bound persona."""

        return self.persona.character_id

    @property
    def display_name(self) -> str:
        """Return the display identity owned by the bound persona."""

        return self.persona.display_name


def generate_participant_reply(
    *,
    participant: ConversationParticipant,
    history: Sequence[Message],
    topic: str,
    run_id: str,
    turn_index: int,
    timestamp: datetime,
) -> Message:
    """Delegate one reply using one participant's inseparable binding."""

    return generate_reply(
        persona=participant.persona,
        history=history,
        topic=topic,
        run_id=run_id,
        turn_index=turn_index,
        provider=participant.provider,
        provider_name=participant.provider_name,
        model_name=participant.model_name,
        timestamp=timestamp,
    )
