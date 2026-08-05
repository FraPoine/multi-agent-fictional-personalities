"""Tests for the conversation run schema."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models.conversation import ConversationRun
from multi_agent_personalities.models.message import Message


def make_message(
    turn_index: int = 0, run_id: str = "run_001", speaker: str = "sherlock_holmes"
) -> dict:
    return {
        "message_id": f"msg_{turn_index:03d}",
        "run_id": run_id,
        "turn_index": turn_index,
        "speaker_character_id": speaker,
        "speaker_name": (
            "Sherlock Holmes" if speaker == "sherlock_holmes" else "Hercule Poirot"
        ),
        "text": "A most revealing observation.",
        "provider": "mock",
        "model": None,
        "timestamp": datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
        "error": None,
    }


@pytest.fixture
def valid_conversation() -> dict:
    return {
        "run_id": "run_001",
        "topic": "How should we investigate the locked room?",
        "character_ids": ["sherlock_holmes", "hercule_poirot"],
        "turn_count": 2,
        "seed": 42,
        "provider": "mock",
        "model": None,
        "created_at": datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
        "status": "completed",
        "messages": [
            make_message(),
            make_message(1, speaker="hercule_poirot"),
        ],
    }


def test_valid_conversation_is_accepted(valid_conversation: dict) -> None:
    conversation = ConversationRun.model_validate(valid_conversation)

    assert conversation.character_ids == (
        "sherlock_holmes",
        "hercule_poirot",
    )
    assert isinstance(conversation.messages, tuple)
    assert all(isinstance(message, Message) for message in conversation.messages)


def test_fields_cannot_be_reassigned(valid_conversation: dict) -> None:
    conversation = ConversationRun.model_validate(valid_conversation)

    with pytest.raises(ValidationError):
        conversation.status = "failed"
    with pytest.raises(ValidationError):
        conversation.messages = ()


def test_contained_messages_cannot_be_modified(
    valid_conversation: dict,
) -> None:
    conversation = ConversationRun.model_validate(valid_conversation)
    with pytest.raises(ValidationError):
        conversation.messages[0].text = "A changed observation."


def test_message_and_character_collections_cannot_be_mutated(
    valid_conversation: dict,
) -> None:
    conversation = ConversationRun.model_validate(valid_conversation)

    with pytest.raises(AttributeError):
        conversation.messages.append(make_message(2))  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        conversation.character_ids[0] = "l"  # type: ignore[index]


def test_serialization_uses_json_arrays(valid_conversation: dict) -> None:
    conversation = ConversationRun.model_validate(valid_conversation)
    serialized = conversation.model_dump(mode="json")

    assert isinstance(serialized["character_ids"], list)
    assert isinstance(serialized["messages"], list)


def test_legacy_run_messages_load_without_generation_metadata(
    valid_conversation: dict,
) -> None:
    conversation = ConversationRun.model_validate(valid_conversation)
    assert all(
        message.generation_metadata is None
        for message in conversation.messages
    )


def test_run_round_trip_preserves_nested_generation_metadata(
    valid_conversation: dict,
) -> None:
    for message in valid_conversation["messages"]:
        message["model"] = "mock-round-robin"
        message["generation_metadata"] = {
            "provider": "mock",
            "model": None,
            "usage": None,
            "finish_reason": "completed",
            "request_id": None,
            "latency_ms": None,
            "retry_count": 0,
        }
    valid_conversation["model"] = "mock-round-robin"

    conversation = ConversationRun.model_validate(valid_conversation)
    restored = ConversationRun.model_validate_json(
        conversation.model_dump_json()
    )

    assert restored == conversation
    assert isinstance(restored.messages, tuple)
    assert all(
        message.generation_metadata is not None
        and message.generation_metadata.provider == "mock"
        for message in restored.messages
    )


def test_only_one_character_is_rejected(valid_conversation: dict) -> None:
    valid_conversation["character_ids"] = ["sherlock_holmes"]

    with pytest.raises(ValidationError):
        ConversationRun.model_validate(valid_conversation)


def test_duplicate_character_ids_are_rejected(valid_conversation: dict) -> None:
    valid_conversation["character_ids"] = [
        "sherlock_holmes",
        "sherlock_holmes",
    ]

    with pytest.raises(ValidationError):
        ConversationRun.model_validate(valid_conversation)


def test_empty_topic_is_rejected(valid_conversation: dict) -> None:
    valid_conversation["topic"] = " "

    with pytest.raises(ValidationError):
        ConversationRun.model_validate(valid_conversation)


def test_zero_turn_count_is_rejected(valid_conversation: dict) -> None:
    valid_conversation["turn_count"] = 0

    with pytest.raises(ValidationError):
        ConversationRun.model_validate(valid_conversation)


def test_naive_created_at_is_rejected(valid_conversation: dict) -> None:
    valid_conversation["created_at"] = datetime(2026, 7, 30, 12, 0)

    with pytest.raises(ValidationError):
        ConversationRun.model_validate(valid_conversation)


def test_message_from_another_run_is_rejected(valid_conversation: dict) -> None:
    valid_conversation["messages"][0]["run_id"] = "run_other"

    with pytest.raises(ValidationError):
        ConversationRun.model_validate(valid_conversation)


def test_message_provider_must_match_run_provider(
    valid_conversation: dict,
) -> None:
    valid_conversation["messages"][0]["provider"] = "another-provider"
    with pytest.raises(ValidationError, match="conversation provider"):
        ConversationRun.model_validate(valid_conversation)


@pytest.mark.parametrize(
    ("run_model", "message_model"),
    [
        ("model-a", "model-b"),
        (None, "model-a"),
        ("model-a", None),
    ],
)
def test_message_model_must_match_run_model(
    valid_conversation: dict,
    run_model: str | None,
    message_model: str | None,
) -> None:
    valid_conversation["model"] = run_model
    valid_conversation["messages"][0]["model"] = message_model
    valid_conversation["messages"][1]["model"] = run_model
    with pytest.raises(ValidationError, match="conversation model"):
        ConversationRun.model_validate(valid_conversation)


def test_failed_legacy_run_with_coherent_error_message_is_valid(
    valid_conversation: dict,
) -> None:
    failed_message = make_message()
    failed_message.update(text="", error="provider unavailable")
    valid_conversation.update(
        status="failed",
        messages=[failed_message],
    )
    conversation = ConversationRun.model_validate(valid_conversation)
    assert conversation.messages[0].generation_metadata is None
    assert conversation.messages[0].error == "provider unavailable"


def test_duplicate_message_turn_indexes_are_rejected(
    valid_conversation: dict,
) -> None:
    valid_conversation["messages"][1]["turn_index"] = 0

    with pytest.raises(ValidationError):
        ConversationRun.model_validate(valid_conversation)


def test_reversed_messages_are_rejected(valid_conversation: dict) -> None:
    valid_conversation["messages"].reverse()

    with pytest.raises(ValidationError, match="chronological sequence"):
        ConversationRun.model_validate(valid_conversation)


def test_missing_middle_turn_is_rejected(valid_conversation: dict) -> None:
    valid_conversation["turn_count"] = 3
    valid_conversation["status"] = "running"
    valid_conversation["messages"] = [make_message(0), make_message(2)]

    with pytest.raises(ValidationError, match="chronological sequence"):
        ConversationRun.model_validate(valid_conversation)


def test_first_message_at_turn_one_is_rejected(
    valid_conversation: dict,
) -> None:
    valid_conversation["status"] = "running"
    valid_conversation["messages"] = [make_message(1)]

    with pytest.raises(ValidationError, match="chronological sequence"):
        ConversationRun.model_validate(valid_conversation)


def test_more_messages_than_turn_count_are_rejected(
    valid_conversation: dict,
) -> None:
    valid_conversation["turn_count"] = 1

    with pytest.raises(ValidationError):
        ConversationRun.model_validate(valid_conversation)


def test_message_turn_index_at_turn_count_is_rejected(
    valid_conversation: dict,
) -> None:
    valid_conversation["status"] = "running"
    valid_conversation["messages"] = [make_message(2)]

    with pytest.raises(ValidationError, match="turn_count - 1"):
        ConversationRun.model_validate(valid_conversation)


def test_message_from_non_participant_is_rejected(
    valid_conversation: dict,
) -> None:
    valid_conversation["messages"][0] = make_message(
        speaker="professor_layton"
    )

    with pytest.raises(ValidationError, match="conversation participants"):
        ConversationRun.model_validate(valid_conversation)


def test_incomplete_completed_conversation_is_rejected(
    valid_conversation: dict,
) -> None:
    valid_conversation["messages"] = [make_message()]

    with pytest.raises(ValidationError, match="completed conversations"):
        ConversationRun.model_validate(valid_conversation)


def test_incomplete_running_conversation_is_accepted(
    valid_conversation: dict,
) -> None:
    valid_conversation["status"] = "running"
    valid_conversation["messages"] = [make_message()]

    conversation = ConversationRun.model_validate(valid_conversation)

    assert len(conversation.messages) == 1


def test_incomplete_failed_conversation_is_accepted(
    valid_conversation: dict,
) -> None:
    valid_conversation["status"] = "failed"
    valid_conversation["messages"] = [make_message()]

    conversation = ConversationRun.model_validate(valid_conversation)

    assert len(conversation.messages) == 1


def test_valid_completed_conversation_remains_accepted(
    valid_conversation: dict,
) -> None:
    conversation = ConversationRun.model_validate(valid_conversation)

    assert conversation.status == "completed"
    assert len(conversation.messages) == conversation.turn_count
