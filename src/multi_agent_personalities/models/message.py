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
        """Require message text unless generation recorded an error."""
        if self.error is None and not self.text.strip():
            raise ValueError("text must not be empty when error is None")
        return self
