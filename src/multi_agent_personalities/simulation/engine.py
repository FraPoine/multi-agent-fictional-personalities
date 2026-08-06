"""Selector-driven conversation simulation engine."""

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
from multi_agent_personalities.simulation.reply_generation import (
    TurnReplyGenerator,
)
from multi_agent_personalities.simulation.speaker_selector import (
    SpeakerSelector,
    select_valid_speaker,
)


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def simulate_chat(
    *,
    participants: Sequence[ConversationParticipant],
    speaker_selector: SpeakerSelector,
    topic: str,
    turn_count: int,
    seed: int,
    run_id: str | None = None,
    timestamp: datetime | None = None,
    turn_reply_generator: TurnReplyGenerator | None = None,
) -> ConversationRun:
    """Generate a complete conversation using an injected speaker selector.

    ``created_at`` marks the run start. Every message receives the same
    timestamp in this deterministic mock implementation; provider-specific
    timing can be introduced later without clock calls inside the turn loop.
    """
    if len(participants) < 2:
        raise ValueError("at least two participants are required")
    participant_ids = tuple(
        participant.character_id for participant in participants
    )
    if len(participant_ids) != len(set(participant_ids)):
        raise ValueError("participants must have unique character_id values")
    participant_by_id = {
        participant.character_id: participant for participant in participants
    }
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
    using_custom_reply_generator = turn_reply_generator is not None
    reply_generator = (
        generate_participant_reply
        if turn_reply_generator is None
        else turn_reply_generator
    )

    history: list[Message] = []
    generated_message_ids: set[str] = set()
    for turn_index in range(turn_count):
        selected_character_id = select_valid_speaker(
            speaker_selector,
            participant_ids=participant_ids,
            history=tuple(history),
            turn_index=turn_index,
        )
        participant = participant_by_id[selected_character_id]
        generated_message = reply_generator(
            participant=participant,
            history=tuple(history),
            topic=topic,
            run_id=resolved_run_id,
            turn_index=turn_index,
            timestamp=created_at,
        )
        if not isinstance(generated_message, Message):
            raise ValueError("turn reply generator must return a Message")
        if using_custom_reply_generator:
            generated_message = Message.model_validate(
                generated_message.model_dump(mode="python")
            )
        if generated_message.run_id != resolved_run_id:
            raise ValueError("generated message run_id must match the current run")
        if generated_message.turn_index != turn_index:
            raise ValueError(
                "generated message turn_index must match the current turn"
            )
        if generated_message.speaker_character_id != selected_character_id:
            raise ValueError(
                "generated message speaker must match the selected participant"
            )
        if generated_message.speaker_name != participant.display_name:
            raise ValueError(
                "generated message speaker_name must match the selected participant"
            )
        if generated_message.provider != participant.provider_name:
            raise ValueError(
                "generated message provider must match the selected participant"
            )
        if (
            participant.model_name is not None
            and generated_message.model != participant.model_name
        ):
            raise ValueError(
                "generated message model must match the selected participant"
            )
        if generated_message.message_id in generated_message_ids:
            raise ValueError("generated message_id values must be unique")
        generated_message_ids.add(generated_message.message_id)
        history.append(generated_message)

    message_providers = {message.provider for message in history}
    if len(message_providers) != 1:
        raise ValueError("generated messages must use one uniform provider")
    effective_provider = history[0].provider
    if effective_provider != provider_name:
        raise ValueError(
            "generated message provider must match the declared provider"
        )

    message_models = {message.model for message in history}
    if len(message_models) != 1:
        raise ValueError("generated messages must use one uniform model")
    effective_model = history[0].model
    if model_name is not None and effective_model != model_name:
        raise ValueError(
            "generated message model must match the declared model"
        )

    return ConversationRun(
        run_id=resolved_run_id,
        topic=topic,
        character_ids=participant_ids,
        turn_count=turn_count,
        seed=seed,
        provider=effective_provider,
        model=effective_model,
        created_at=created_at,
        status="completed",
        messages=tuple(history),
    )
