"""Immutable building blocks for revealed investigation information."""

from collections.abc import Sequence
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)


NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]
NonNegativeStrictInt = Annotated[int, Field(strict=True, ge=0)]


class EvidenceRelation(str, Enum):
    """Allowed relationships between future reasoning and a revealed clue."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class HypothesisStatus(str, Enum):
    """Lifecycle states for immutable hypothesis records."""

    ACTIVE = "active"
    DISCARDED = "discarded"


class GroupDecisionType(str, Enum):
    """Explicit actions that an investigation group may adopt."""

    PURSUE_LEAD = "pursue_lead"
    ADOPT_HYPOTHESIS = "adopt_hypothesis"
    DISCARD_HYPOTHESIS = "discard_hypothesis"
    REQUEST_INFORMATION = "request_information"


class Clue(BaseModel):
    """Information explicitly revealed by the game master."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    clue_id: NonEmptyStr
    text: StrictStr
    reveal_order: NonNegativeStrictInt

    @field_validator("text")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        """Reject blank clue text while preserving its original form."""
        if not value.strip():
            raise ValueError("clue text must not be empty")
        return value


class EvidenceReference(BaseModel):
    """A stable clue reference used by future investigation models."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    clue_id: NonEmptyStr
    relation: EvidenceRelation


def _reject_duplicate_strings(
    values: tuple[str, ...],
    field_name: str,
) -> tuple[str, ...]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values


def _reject_duplicate_evidence(
    values: tuple[EvidenceReference, ...],
) -> tuple[EvidenceReference, ...]:
    keys = [(item.clue_id, item.relation) for item in values]
    if len(keys) != len(set(keys)):
        raise ValueError("evidence must not contain duplicate references")
    return values


class AgentAnalysis(BaseModel):
    """One agent's facts, deductions, evidence, and suggested leads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_id: NonEmptyStr
    agent_id: NonEmptyStr
    facts: tuple[NonEmptyStr, ...] = ()
    deductions: tuple[NonEmptyStr, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    proposed_leads: tuple[NonEmptyStr, ...] = ()

    @field_validator("facts", "deductions", "proposed_leads")
    @classmethod
    def validate_unique_text_entries(
        cls,
        value: tuple[str, ...],
        info: ValidationInfo,
    ) -> tuple[str, ...]:
        """Reject repeated entries while retaining their supplied order."""
        return _reject_duplicate_strings(value, info.field_name)

    @field_validator("evidence")
    @classmethod
    def validate_unique_evidence(
        cls,
        value: tuple[EvidenceReference, ...],
    ) -> tuple[EvidenceReference, ...]:
        return _reject_duplicate_evidence(value)

    @model_validator(mode="after")
    def validate_reasoning_content(self) -> "AgentAnalysis":
        """Require an observation, deduction, or proposed next step."""
        if not (self.facts or self.deductions or self.proposed_leads):
            raise ValueError(
                "analysis requires at least one fact, deduction, or proposed lead"
            )
        return self


class Hypothesis(BaseModel):
    """An immutable hypothesis, optionally revising an earlier record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: NonEmptyStr
    statement: StrictStr
    status: HypothesisStatus
    evidence: tuple[EvidenceReference, ...] = ()
    previous_hypothesis_id: NonEmptyStr | None = None

    @field_validator("statement")
    @classmethod
    def validate_statement(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("hypothesis statement must not be empty")
        return value

    @field_validator("evidence")
    @classmethod
    def validate_unique_evidence(
        cls,
        value: tuple[EvidenceReference, ...],
    ) -> tuple[EvidenceReference, ...]:
        return _reject_duplicate_evidence(value)

    @model_validator(mode="after")
    def validate_revision_reference(self) -> "Hypothesis":
        if self.previous_hypothesis_id == self.hypothesis_id:
            raise ValueError("a hypothesis cannot reference itself as previous")
        return self


class GroupDecision(BaseModel):
    """A decision explicitly adopted by the investigation group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: NonEmptyStr
    decision_type: GroupDecisionType
    summary: StrictStr
    analysis_ids: tuple[NonEmptyStr, ...] = ()
    hypothesis_ids: tuple[NonEmptyStr, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()

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

    @field_validator("evidence")
    @classmethod
    def validate_unique_evidence(
        cls,
        value: tuple[EvidenceReference, ...],
    ) -> tuple[EvidenceReference, ...]:
        return _reject_duplicate_evidence(value)


def validate_unique_clue_ids(clues: Sequence[Clue]) -> tuple[Clue, ...]:
    """Return clues in input order after rejecting duplicate identifiers."""
    validated = tuple(clues)
    clue_ids = [clue.clue_id for clue in validated]
    if len(clue_ids) != len(set(clue_ids)):
        raise ValueError("clue_id values must be unique")
    return validated
