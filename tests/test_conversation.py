"""Tests for the conversation run schema."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models.conversation import ConversationRun


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

    assert conversation.character_ids == ["sherlock_holmes", "hercule_poirot"]


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


def test_duplicate_message_turn_indexes_are_rejected(
    valid_conversation: dict,
) -> None:
    valid_conversation["messages"][1]["turn_index"] = 0

    with pytest.raises(ValidationError):
        ConversationRun.model_validate(valid_conversation)


def test_more_messages_than_turn_count_are_rejected(
    valid_conversation: dict,
) -> None:
    valid_conversation["turn_count"] = 1

    with pytest.raises(ValidationError):
        ConversationRun.model_validate(valid_conversation)


def test_incomplete_running_conversation_is_accepted(
    valid_conversation: dict,
) -> None:
    valid_conversation["status"] = "running"
    valid_conversation["messages"] = [make_message()]

    conversation = ConversationRun.model_validate(valid_conversation)

    assert len(conversation.messages) == 1
