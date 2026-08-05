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
    field_validator,
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


def validate_unique_clue_ids(clues: Sequence[Clue]) -> tuple[Clue, ...]:
    """Return clues in input order after rejecting duplicate identifiers."""
    validated = tuple(clues)
    clue_ids = [clue.clue_id for clue in validated]
    if len(clue_ids) != len(set(clue_ids)):
        raise ValueError("clue_id values must be unique")
    return validated
