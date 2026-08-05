"""Schema for messages generated during a conversation."""

from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from multi_agent_personalities.models.generation import GenerationMetadata


NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]


class Message(BaseModel):
    """One generated message in a conversation run."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    message_id: NonEmptyStr
    run_id: NonEmptyStr
    turn_index: int
    speaker_character_id: NonEmptyStr
    speaker_name: NonEmptyStr
    text: StrictStr
    provider: NonEmptyStr
    model: StrictStr | None = None
    generation_metadata: GenerationMetadata | None = None
    timestamp: datetime
    error: StrictStr | None = None

    @field_validator("turn_index")
    @classmethod
    def validate_turn_index(cls, value: int) -> int:
        """Reject negative conversation turn indexes."""
        if value < 0:
            raise ValueError("turn_index must be greater than or equal to zero")
        return value

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Require an explicit UTC offset."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_text_or_error(self) -> "Message":
        """Validate successful text and compatibility metadata mirrors."""
        if self.error is None and not self.text.strip():
            raise ValueError("text must not be empty when error is None")
        if self.error is not None and self.generation_metadata is not None:
            raise ValueError(
                "failed messages must not contain successful generation metadata"
            )
        if self.generation_metadata is None:
            return self
        if self.provider != self.generation_metadata.provider:
            raise ValueError(
                "message provider must match generation metadata provider"
            )
        reported_model = self.generation_metadata.model
        if reported_model is not None and self.model != reported_model:
            raise ValueError(
                "message model must match reported generation metadata model"
            )
        return self
