"""Provider-neutral structured-output validation for investigation content."""

from typing import Annotated, Generic, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictStr,
    StringConstraints,
    ValidationError,
    ValidationInfo,
    field_validator,
)

from multi_agent_personalities.models import (
    EvidenceReference,
    GenerationResult,
    GroupDecisionType,
    HypothesisStatus,
)


NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]


def _reject_duplicate_strings(
    values: tuple[str, ...],
    field_name: str,
) -> tuple[str, ...]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values


class GeneratedHypothesisPayload(BaseModel):
    """Provider-authored hypothesis content without authoritative identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: StrictStr
    status: HypothesisStatus
    evidence: tuple[EvidenceReference, ...]
    previous_hypothesis_id: NonEmptyStr | None = None

    @field_validator("statement")
    @classmethod
    def validate_statement(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("hypothesis statement must not be empty")
        return value


class GeneratedAnalysisPayload(BaseModel):
    """Provider-authored analysis content awaiting service enrichment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facts: tuple[NonEmptyStr, ...]
    deductions: tuple[NonEmptyStr, ...]
    evidence: tuple[EvidenceReference, ...]
    proposed_leads: tuple[NonEmptyStr, ...]
    hypotheses: tuple[GeneratedHypothesisPayload, ...] = ()

    @field_validator("facts", "deductions", "proposed_leads")
    @classmethod
    def validate_unique_text(
        cls,
        value: tuple[str, ...],
        info: ValidationInfo,
    ) -> tuple[str, ...]:
        return _reject_duplicate_strings(value, info.field_name)


class GeneratedDecisionPayload(BaseModel):
    """Provider-authored group-decision content without owning IDs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_type: GroupDecisionType
    summary: StrictStr
    analysis_ids: tuple[NonEmptyStr, ...]
    hypothesis_ids: tuple[NonEmptyStr, ...]
    evidence: tuple[EvidenceReference, ...]
    hypotheses: tuple[GeneratedHypothesisPayload, ...] = ()

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("group decision summary must not be empty")
        return value

    @field_validator("analysis_ids", "hypothesis_ids")
    @classmethod
    def validate_unique_ids(
        cls,
        value: tuple[str, ...],
        info: ValidationInfo,
    ) -> tuple[str, ...]:
        return _reject_duplicate_strings(value, info.field_name)


class GeneratedFinalTheoryPayload(BaseModel):
    """Provider-authored final-theory content without authoritative identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: StrictStr
    hypothesis_ids: tuple[NonEmptyStr, ...]
    evidence: tuple[EvidenceReference, ...]

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("final theory summary must not be empty")
        return value

    @field_validator("hypothesis_ids")
    @classmethod
    def validate_unique_hypothesis_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _reject_duplicate_strings(value, "hypothesis_ids")


T = TypeVar("T", bound=BaseModel)


class StructuredGenerationResult(BaseModel, Generic[T]):
    """Validated provider content paired with its exact generation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: T
    generation: GenerationResult


class StructuredOutputError(ValueError):
    """Raised when generated JSON is malformed or violates its output schema."""


def parse_structured_generation(
    generation: GenerationResult,
    output_model: type[T],
) -> StructuredGenerationResult[T]:
    """Validate exact generated text as JSON without extraction or repair."""
    if not isinstance(generation, GenerationResult):
        raise StructuredOutputError("generation must be a GenerationResult")
    if not generation.text.strip():
        raise StructuredOutputError("generated structured output is empty")
    if not isinstance(output_model, type) or not issubclass(output_model, BaseModel):
        raise StructuredOutputError("output_model must be a Pydantic model type")

    try:
        value = output_model.model_validate_json(generation.text)
    except ValidationError as error:
        error_types = {item["type"] for item in error.errors()}
        category = "malformed JSON" if "json_invalid" in error_types else "invalid schema"
        raise StructuredOutputError(
            f"generated structured output contains {category}"
        ) from error
    return StructuredGenerationResult(value=value, generation=generation)
