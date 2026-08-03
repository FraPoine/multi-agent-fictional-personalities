"""Round-robin conversation simulation engine."""

from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

from multi_agent_personalities.agent_runtime import generate_reply
from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.models.conversation import ConversationRun
from multi_agent_personalities.models.message import Message
from multi_agent_personalities.models.persona import Persona


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def simulate_chat(
    *,
    personas: Sequence[Persona],
    topic: str,
    turn_count: int,
    provider: LLMProvider,
    provider_name: str,
    seed: int,
    model_name: str | None = None,
    run_id: str | None = None,
    timestamp: datetime | None = None,
) -> ConversationRun:
    """Generate a complete conversation using fixed round-robin speakers.

    ``created_at`` marks the run start. Every message receives the same
    timestamp in this deterministic mock implementation; provider-specific
    timing can be introduced later without clock calls inside the turn loop.
    """
    if len(personas) < 2:
        raise ValueError("at least two personas are required")
    character_ids = tuple(persona.character_id for persona in personas)
    if len(character_ids) != len(set(character_ids)):
        raise ValueError("personas must have unique character_id values")
    _require_non_empty(topic, "topic")
    _require_non_empty(provider_name, "provider_name")
    if turn_count <= 0:
        raise ValueError("turn_count must be greater than zero")
    if run_id is not None:
        _require_non_empty(run_id, "run_id")

    created_at = timestamp or datetime.now(timezone.utc)
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    resolved_run_id = run_id or uuid4().hex

    history: list[Message] = []
    for turn_index in range(turn_count):
        persona = personas[turn_index % len(personas)]
        history.append(
            generate_reply(
                persona=persona,
                history=history,
                topic=topic,
                run_id=resolved_run_id,
                turn_index=turn_index,
                provider=provider,
                provider_name=provider_name,
                model_name=model_name,
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
