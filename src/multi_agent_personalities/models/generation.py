"""Provider-neutral schemas for successful text generation results."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


NonNegativeStrictInt = Annotated[int, Field(strict=True, ge=0)]
NonNegativeFloat = Annotated[float, Field(strict=True, ge=0)]


class TokenUsage(BaseModel):
    """Optional provider-reported input and output token counters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: NonNegativeStrictInt | None = None
    output_tokens: NonNegativeStrictInt | None = None


class GenerationMetadata(BaseModel):
    """Provider-neutral metadata for one successful generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: StrictStr
    model: StrictStr | None = None
    usage: TokenUsage | None = None
    finish_reason: StrictStr | None = None
    request_id: StrictStr | None = None
    latency_ms: NonNegativeFloat | None = None
    retry_count: NonNegativeStrictInt = 0

    @field_validator("provider", "model", "finish_reason", "request_id")
    @classmethod
    def validate_non_empty_strings(cls, value: str | None) -> str | None:
        """Reject empty supplied metadata strings without rewriting them."""

        if value is not None and not value.strip():
            raise ValueError("generation metadata strings must not be empty")
        return value


class GenerationResult(BaseModel):
    """Validated successful generated text and its structured metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: StrictStr
    metadata: GenerationMetadata

    @field_validator("text")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        """Require visible generated content while preserving exact text."""

        if not value.strip():
            raise ValueError("text must not be empty")
        return value
