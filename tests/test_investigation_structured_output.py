"""Tests for investigation structured-output parsing and provenance."""

import json

import pytest
from pydantic import ValidationError

from multi_agent_personalities.application import (
    GeneratedAnalysisPayload,
    GeneratedDecisionPayload,
    GeneratedFinalTheoryPayload,
    StructuredGenerationResult,
    StructuredOutputError,
    parse_structured_generation,
)
from multi_agent_personalities.models import (
    GenerationMetadata,
    GenerationResult,
    GroupDecisionType,
    TokenUsage,
)


def generation(text: str) -> GenerationResult:
    return GenerationResult(
        text=text,
        metadata=GenerationMetadata(
            provider="mock",
            model="mock-model",
            usage=TokenUsage(input_tokens=12, output_tokens=8),
            finish_reason="stop",
            request_id="request_001",
            latency_ms=1.25,
            retry_count=0,
        ),
    )


def analysis_json(**overrides: object) -> str:
    payload: dict[str, object] = {
        "facts": ["The window is open."],
        "deductions": ["Someone may have exited."],
        "evidence": [{"clue_id": "clue_001", "relation": "supports"}],
        "proposed_leads": ["Inspect the garden."],
    }
    payload.update(overrides)
    return json.dumps(payload)


def decision_json(**overrides: object) -> str:
    payload: dict[str, object] = {
        "decision_type": "request_information",
        "summary": "Ask for another clue.",
        "analysis_ids": ["analysis_001"],
        "hypothesis_ids": [],
        "evidence": [{"clue_id": "clue_001", "relation": "context"}],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_valid_json_produces_typed_immutable_payload_and_tuples() -> None:
    result = parse_structured_generation(
        generation(analysis_json()),
        GeneratedAnalysisPayload,
    )

    assert isinstance(result, StructuredGenerationResult)
    assert isinstance(result.value, GeneratedAnalysisPayload)
    assert result.value.facts == ("The window is open.",)
    assert result.value.proposed_leads == ("Inspect the garden.",)
    with pytest.raises(ValidationError):
        result.value.facts = ()


@pytest.mark.parametrize("text", ["{", "not json", "```json\n{}\n```"])
def test_malformed_or_markdown_wrapped_json_is_not_repaired(text: str) -> None:
    with pytest.raises(StructuredOutputError, match="malformed JSON") as caught:
        parse_structured_generation(generation(text), GeneratedAnalysisPayload)
    assert caught.value.__cause__ is not None


@pytest.mark.parametrize(
    "text",
    [
        json.dumps({"facts": []}),
        analysis_json(facts="not a list"),
        analysis_json(extra="not allowed"),
        analysis_json(evidence=[{"clue_id": "clue_001", "relation": "invalid"}]),
    ],
)
def test_schema_invalid_json_fails_without_fallback(text: str) -> None:
    with pytest.raises(StructuredOutputError, match="invalid schema") as caught:
        parse_structured_generation(generation(text), GeneratedAnalysisPayload)
    assert caught.value.__cause__ is not None


def test_invalid_decision_enum_is_rejected() -> None:
    with pytest.raises(StructuredOutputError, match="invalid schema"):
        parse_structured_generation(
            generation(decision_json(decision_type="vote")),
            GeneratedDecisionPayload,
        )


def test_adapter_preserves_original_generation_and_metadata_exactly() -> None:
    original = generation(decision_json())
    result = parse_structured_generation(original, GeneratedDecisionPayload)

    assert result.generation is original
    assert result.generation.text == original.text
    assert result.generation.metadata is original.metadata
    assert result.generation.metadata.provider == "mock"
    assert result.generation.metadata.model == "mock-model"
    assert result.generation.metadata.usage == TokenUsage(
        input_tokens=12,
        output_tokens=8,
    )
    assert result.value.decision_type is GroupDecisionType.REQUEST_INFORMATION


def test_same_adapter_validates_multiple_output_models() -> None:
    analysis = parse_structured_generation(
        generation(analysis_json()), GeneratedAnalysisPayload
    )
    final = parse_structured_generation(
        generation(
            json.dumps(
                {
                    "summary": "The visitor escaped through the window.",
                    "hypothesis_ids": ["hypothesis_001"],
                    "evidence": [
                        {"clue_id": "clue_001", "relation": "supports"}
                    ],
                }
            )
        ),
        GeneratedFinalTheoryPayload,
    )

    assert isinstance(analysis.value, GeneratedAnalysisPayload)
    assert isinstance(final.value, GeneratedFinalTheoryPayload)


def test_provider_name_does_not_change_adapter_path() -> None:
    mock = generation(analysis_json())
    provider_independent = GenerationResult(
        text=mock.text,
        metadata=GenerationMetadata(provider="future-provider", model="model-x"),
    )

    assert parse_structured_generation(
        mock, GeneratedAnalysisPayload
    ).value == parse_structured_generation(
        provider_independent, GeneratedAnalysisPayload
    ).value


def test_empty_or_whitespace_text_fails_even_for_unchecked_legacy_instance() -> None:
    unchecked = GenerationResult.model_construct(
        text="  \n",
        metadata=GenerationMetadata(provider="mock"),
    )
    with pytest.raises(StructuredOutputError, match="empty"):
        parse_structured_generation(unchecked, GeneratedAnalysisPayload)


def test_payload_schemas_omit_authoritative_identity_fields() -> None:
    forbidden = {
        "session_id", "round_id", "analysis_id", "hypothesis_id",
        "decision_id", "final_theory_id",
    }
    for model in (
        GeneratedAnalysisPayload,
        GeneratedDecisionPayload,
        GeneratedFinalTheoryPayload,
    ):
        assert forbidden.isdisjoint(model.model_fields)
