"""Tests for the conversation message schema."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models.message import Message


@pytest.fixture
def valid_message() -> dict:
    return {
        "message_id": "msg_001",
        "run_id": "run_001",
        "turn_index": 0,
        "speaker_character_id": "sherlock_holmes",
        "speaker_name": "Sherlock Holmes",
        "text": "The evidence permits only one conclusion.",
        "provider": "mock",
        "model": None,
        "timestamp": datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
        "error": None,
    }


def test_valid_message_is_accepted(valid_message: dict) -> None:
    message = Message.model_validate(valid_message)

    assert message.speaker_character_id == "sherlock_holmes"


@pytest.mark.parametrize(
    ("field", "value"),
    [("text", "A different conclusion."), ("turn_index", 1)],
)
def test_message_fields_cannot_be_reassigned(
    valid_message: dict, field: str, value: object
) -> None:
    message = Message.model_validate(valid_message)
    with pytest.raises(ValidationError):
        setattr(message, field, value)


def test_json_serialization_still_works(valid_message: dict) -> None:
    serialized = Message.model_validate(valid_message).model_dump_json()
    assert '"message_id":"msg_001"' in serialized
    assert '"timestamp":"2026-07-30T12:00:00Z"' in serialized


def test_negative_turn_index_is_rejected(valid_message: dict) -> None:
    valid_message["turn_index"] = -1

    with pytest.raises(ValidationError):
        Message.model_validate(valid_message)


def test_empty_message_id_is_rejected(valid_message: dict) -> None:
    valid_message["message_id"] = " "

    with pytest.raises(ValidationError):
        Message.model_validate(valid_message)


@pytest.mark.parametrize("field", ["speaker_character_id", "speaker_name"])
def test_empty_speaker_fields_are_rejected(
    valid_message: dict, field: str
) -> None:
    valid_message[field] = " "

    with pytest.raises(ValidationError):
        Message.model_validate(valid_message)


def test_naive_timestamp_is_rejected(valid_message: dict) -> None:
    valid_message["timestamp"] = datetime(2026, 7, 30, 12, 0)

    with pytest.raises(ValidationError):
        Message.model_validate(valid_message)


def test_empty_text_without_error_is_rejected(valid_message: dict) -> None:
    valid_message["text"] = " "

    with pytest.raises(ValidationError):
        Message.model_validate(valid_message)


def test_empty_text_with_error_is_accepted(valid_message: dict) -> None:
    valid_message["text"] = ""
    valid_message["error"] = "Provider request failed."

    message = Message.model_validate(valid_message)

    assert message.text == ""
