"""Round-robin conversation simulation engine."""

from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

from multi_agent_personalities.models.conversation import ConversationRun
from multi_agent_personalities.models.identifiers import validate_run_id
from multi_agent_personalities.models.message import Message
from multi_agent_personalities.simulation.participant import (
    ConversationParticipant,
    generate_participant_reply,
)


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def simulate_chat(
    *,
    participants: Sequence[ConversationParticipant],
    topic: str,
    turn_count: int,
    seed: int,
    run_id: str | None = None,
    timestamp: datetime | None = None,
) -> ConversationRun:
    """Generate a complete conversation using fixed round-robin speakers.

    ``created_at`` marks the run start. Every message receives the same
    timestamp in this deterministic mock implementation; provider-specific
    timing can be introduced later without clock calls inside the turn loop.
    """
    if len(participants) < 2:
        raise ValueError("at least two participants are required")
    character_ids = tuple(participant.character_id for participant in participants)
    if len(character_ids) != len(set(character_ids)):
        raise ValueError("participants must have unique character_id values")
    _require_non_empty(topic, "topic")
    if turn_count <= 0:
        raise ValueError("turn_count must be greater than zero")
    if run_id is not None:
        validate_run_id(run_id)

    provider_names = {participant.provider_name for participant in participants}
    if len(provider_names) != 1:
        raise ValueError("participants must use one uniform provider_name")
    model_names = {participant.model_name for participant in participants}
    if len(model_names) != 1:
        raise ValueError("participants must use one uniform model_name")
    provider_name = participants[0].provider_name
    model_name = participants[0].model_name

    created_at = timestamp or datetime.now(timezone.utc)
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    resolved_run_id = validate_run_id(run_id or uuid4().hex)

    history: list[Message] = []
    for turn_index in range(turn_count):
        participant = participants[turn_index % len(participants)]
        history.append(
            generate_participant_reply(
                participant=participant,
                history=history,
                topic=topic,
                run_id=resolved_run_id,
                turn_index=turn_index,
                timestamp=created_at,
            )
        )

    return ConversationRun(
        run_id=resolved_run_id,
        topic=topic,
        character_ids=character_ids,
        turn_count=turn_count,
        seed=seed,
        provider=provider_name,
        model=model_name,
        created_at=created_at,
        status="completed",
        messages=tuple(history),
    )
