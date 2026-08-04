"""Immutable schemas for blind evaluation pilots."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
CharacterId = Literal["sherlock_holmes", "hercule_poirot"]


class EvaluationTrial(BaseModel):
    """Internal trial with traceability and ground truth."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trial_id: NonEmptyStr
    source_run_id: NonEmptyStr
    source_message_id: NonEmptyStr
    condition: NonEmptyStr
    display_text: NonEmptyStr
    candidate_character_ids: tuple[CharacterId, CharacterId]
    correct_character_id: CharacterId
    source_provider: NonEmptyStr
    synthetic_data: bool

    @field_validator("candidate_character_ids")
    @classmethod
    def validate_candidates(cls, value: tuple[CharacterId, CharacterId]) -> tuple[CharacterId, CharacterId]:
        if len(set(value)) != 2:
            raise ValueError("candidate_character_ids must contain both pilot characters")
        return value

    @model_validator(mode="after")
    def validate_correct_candidate(self) -> "EvaluationTrial":
        if self.correct_character_id not in self.candidate_character_ids:
            raise ValueError("correct_character_id must be a candidate")
        return self

    def public_dict(self) -> dict[str, object]:
        """Return the complete rater-safe representation."""
        return self.model_dump(
            exclude={
                "correct_character_id",
                "source_run_id",
                "source_message_id",
                "source_provider",
            }
        )


class TrialAnswer(BaseModel):
    """Private ground truth and source provenance for one public trial."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    trial_id: NonEmptyStr
    correct_character_id: CharacterId
    source_run_id: NonEmptyStr
    source_message_id: NonEmptyStr


class PublicEvaluationTrial(BaseModel):
    """Rater-facing trial schema, structurally incapable of holding an answer."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    trial_id: NonEmptyStr
    condition: NonEmptyStr
    display_text: NonEmptyStr
    candidate_character_ids: tuple[CharacterId, CharacterId]
    synthetic_data: bool


class RaterResponse(BaseModel):
    """One immutable rater answer."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    response_id: NonEmptyStr
    trial_id: NonEmptyStr
    rater_id: NonEmptyStr
    selected_character_id: CharacterId
    confidence: int = Field(ge=1, le=5)
    timestamp: datetime
    response_duration_seconds: float | None = Field(default=None, ge=0)
    synthetic_data: bool = False

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value
