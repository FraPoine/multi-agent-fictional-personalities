"""Tests for the conversation message schema."""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models import GenerationMetadata, TokenUsage
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
    assert message.generation_metadata is None


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
    assert message.generation_metadata is None


def test_failed_message_with_explicit_null_metadata_is_accepted(
    valid_message: dict,
) -> None:
    valid_message.update(
        text="",
        error="Provider request failed.",
        generation_metadata=None,
    )
    message = Message.model_validate(valid_message)
    assert message.error == "Provider request failed."
    assert message.generation_metadata is None


def test_failed_message_with_success_metadata_is_rejected(
    valid_message: dict,
) -> None:
    valid_message.update(
        text="",
        error="Provider request failed.",
        generation_metadata=GenerationMetadata(provider="mock"),
    )
    with pytest.raises(ValidationError, match="failed messages must not contain"):
        Message.model_validate(valid_message)


def test_complete_generation_metadata_is_preserved_and_round_trips(
    valid_message: dict,
) -> None:
    metadata = GenerationMetadata(
        provider="mock",
        model="reported-model",
        usage=TokenUsage(input_tokens=12, output_tokens=4),
        finish_reason="completed",
        request_id="request-001",
        latency_ms=3.5,
        retry_count=1,
    )
    valid_message["model"] = "reported-model"
    valid_message["generation_metadata"] = metadata

    message = Message.model_validate(valid_message)

    assert message.generation_metadata == metadata
    dumped = message.model_dump(mode="json")
    assert dumped["generation_metadata"] == {
        "provider": "mock",
        "model": "reported-model",
        "usage": {"input_tokens": 12, "output_tokens": 4},
        "finish_reason": "completed",
        "request_id": "request-001",
        "latency_ms": 3.5,
        "retry_count": 1,
    }
    assert json.loads(message.model_dump_json())["generation_metadata"] == (
        dumped["generation_metadata"]
    )
    assert Message.model_validate_json(message.model_dump_json()) == message
    with pytest.raises(ValidationError):
        message.generation_metadata = None


@pytest.mark.parametrize("model", [None, "mock-round-robin"])
def test_partial_metadata_allows_absent_reported_model(
    valid_message: dict,
    model: str | None,
) -> None:
    valid_message["model"] = model
    valid_message["generation_metadata"] = GenerationMetadata(
        provider="mock",
        finish_reason="completed",
    )

    message = Message.model_validate(valid_message)

    assert message.model == model
    assert message.generation_metadata is not None
    assert message.generation_metadata.model is None


def test_generation_metadata_provider_mismatch_is_rejected(
    valid_message: dict,
) -> None:
    valid_message["generation_metadata"] = GenerationMetadata(
        provider="another-provider"
    )
    with pytest.raises(ValidationError, match="provider must match"):
        Message.model_validate(valid_message)


@pytest.mark.parametrize("model", [None, "configured-model"])
def test_reported_model_must_match_top_level_model(
    valid_message: dict,
    model: str | None,
) -> None:
    valid_message["model"] = model
    valid_message["generation_metadata"] = GenerationMetadata(
        provider="mock",
        model="reported-model",
    )
    with pytest.raises(ValidationError, match="model must match"):
        Message.model_validate(valid_message)
