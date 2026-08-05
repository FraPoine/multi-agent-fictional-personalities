"""Tests for provider-neutral successful-generation schemas."""

import json

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models import (
    GenerationMetadata,
    GenerationResult,
    TokenUsage,
)


def complete_result() -> GenerationResult:
    return GenerationResult(
        text="A complete result.",
        metadata=GenerationMetadata(
            provider="test-provider",
            model="test-model",
            usage=TokenUsage(input_tokens=120, output_tokens=35),
            finish_reason="completed",
            request_id="request-001",
            latency_ms=14.5,
            retry_count=1,
        ),
    )


def test_minimal_result_uses_optional_metadata_defaults() -> None:
    result = GenerationResult(
        text="A valid response.",
        metadata=GenerationMetadata(provider="mock"),
    )

    assert result.text == "A valid response."
    assert result.metadata.provider == "mock"
    assert result.metadata.model is None
    assert result.metadata.usage is None
    assert result.metadata.finish_reason is None
    assert result.metadata.request_id is None
    assert result.metadata.latency_ms is None
    assert result.metadata.retry_count == 0


def test_complete_result_preserves_every_field() -> None:
    result = complete_result()

    assert result.text == "A complete result."
    assert result.metadata.provider == "test-provider"
    assert result.metadata.model == "test-model"
    assert result.metadata.usage == TokenUsage(
        input_tokens=120,
        output_tokens=35,
    )
    assert result.metadata.finish_reason == "completed"
    assert result.metadata.request_id == "request-001"
    assert result.metadata.latency_ms == 14.5
    assert result.metadata.retry_count == 1


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_result_text_is_rejected(text: str) -> None:
    with pytest.raises(ValidationError, match="text must not be empty"):
        GenerationResult(
            text=text,
            metadata=GenerationMetadata(provider="mock"),
        )


def test_result_text_whitespace_is_preserved() -> None:
    text = "  A deliberately padded response.\n"
    result = GenerationResult(
        text=text,
        metadata=GenerationMetadata(provider="mock"),
    )
    assert result.text == text


def test_metadata_is_required() -> None:
    with pytest.raises(ValidationError):
        GenerationResult(text="A response.")  # type: ignore[call-arg]


@pytest.mark.parametrize("provider", ["", "   "])
def test_provider_must_not_be_empty(provider: str) -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        GenerationMetadata(provider=provider)


@pytest.mark.parametrize("field", ["model", "finish_reason", "request_id"])
def test_optional_metadata_strings_must_not_be_empty(field: str) -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        GenerationMetadata(provider="mock", **{field: "  "})
    assert GenerationMetadata(provider="mock", **{field: None})


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens"])
def test_negative_token_counts_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        TokenUsage(**{field: -1})


def test_negative_latency_is_rejected() -> None:
    with pytest.raises(ValidationError):
        GenerationMetadata(provider="mock", latency_ms=-0.1)


def test_negative_retry_count_is_rejected() -> None:
    with pytest.raises(ValidationError):
        GenerationMetadata(provider="mock", retry_count=-1)


def test_zero_numeric_values_are_valid() -> None:
    metadata = GenerationMetadata(
        provider="mock",
        usage=TokenUsage(input_tokens=0, output_tokens=0),
        latency_ms=0,
        retry_count=0,
    )
    assert metadata.usage == TokenUsage(input_tokens=0, output_tokens=0)
    assert metadata.latency_ms == 0
    assert metadata.retry_count == 0


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        (TokenUsage(), "input_tokens", 5),
        (GenerationMetadata(provider="mock"), "provider", "changed"),
        (
            GenerationResult(
                text="A response.",
                metadata=GenerationMetadata(provider="mock"),
            ),
            "text",
            "changed",
        ),
    ],
)
def test_models_are_frozen(model: object, field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        setattr(model, field, value)


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        TokenUsage(input_tokens=1, cached_tokens=1)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        GenerationMetadata(provider="mock", cost=0)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        GenerationResult(
            text="A result.",
            metadata=GenerationMetadata(provider="mock"),
            error=None,  # type: ignore[call-arg]
        )


def test_serialization_has_expected_nested_structure() -> None:
    result = complete_result()
    expected = {
        "text": "A complete result.",
        "metadata": {
            "provider": "test-provider",
            "model": "test-model",
            "usage": {"input_tokens": 120, "output_tokens": 35},
            "finish_reason": "completed",
            "request_id": "request-001",
            "latency_ms": 14.5,
            "retry_count": 1,
        },
    }
    assert result.model_dump() == expected
    assert json.loads(result.model_dump_json()) == expected


def test_json_round_trip_preserves_complete_result() -> None:
    result = complete_result()
    assert GenerationResult.model_validate_json(result.model_dump_json()) == result


def test_nested_dictionaries_are_validated_as_models() -> None:
    result = GenerationResult.model_validate(
        {
            "text": "A response.",
            "metadata": {
                "provider": "mock",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        }
    )
    assert isinstance(result.metadata, GenerationMetadata)
    assert isinstance(result.metadata.usage, TokenUsage)


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        (TokenUsage, "input_tokens", True),
        (TokenUsage, "output_tokens", False),
        (GenerationMetadata, "retry_count", True),
    ],
)
def test_counters_reject_booleans(target: type, field: str, value: bool) -> None:
    arguments = {field: value}
    if target is GenerationMetadata:
        arguments["provider"] = "mock"
    with pytest.raises(ValidationError):
        target(**arguments)
