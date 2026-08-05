"""Schema for complete multi-agent conversation runs."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from multi_agent_personalities.models.message import Message


NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]


class ConversationRun(BaseModel):
    """An immutable, validated snapshot of a multi-agent conversation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: NonEmptyStr
    topic: NonEmptyStr
    character_ids: tuple[NonEmptyStr, ...] = Field(min_length=2)
    turn_count: int
    seed: int
    provider: NonEmptyStr
    model: StrictStr | None = None
    created_at: datetime
    status: Literal["running", "completed", "failed"]
    messages: tuple[Message, ...] = ()

    @field_validator("character_ids")
    @classmethod
    def validate_unique_character_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Reject ambiguous participant lists."""
        if len(value) != len(set(value)):
            raise ValueError("character_ids must not contain duplicates")
        return value

    @field_validator("turn_count")
    @classmethod
    def validate_turn_count(cls, value: int) -> int:
        """Require at least one configured turn."""
        if value <= 0:
            raise ValueError("turn_count must be greater than zero")
        return value

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        """Require an explicit UTC offset."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_messages(self) -> "ConversationRun":
        """Ensure stored messages are consistent with their parent run."""
        if any(message.run_id != self.run_id for message in self.messages):
            raise ValueError("all messages must belong to the conversation run_id")

        if any(message.provider != self.provider for message in self.messages):
            raise ValueError("all messages must match the conversation provider")

        if any(message.model != self.model for message in self.messages):
            raise ValueError("all messages must match the conversation model")

        turn_indexes = [message.turn_index for message in self.messages]
        if any(
            not 0 <= turn_index < self.turn_count
            for turn_index in turn_indexes
        ):
            raise ValueError(
                "message turn_index values must be between zero and "
                "turn_count - 1"
            )

        expected_indexes = list(range(len(self.messages)))
        if turn_indexes != expected_indexes:
            raise ValueError(
                "messages must contain a chronological sequence starting "
                "from turn zero"
            )

        if any(
            message.speaker_character_id not in self.character_ids
            for message in self.messages
        ):
            raise ValueError(
                "all message speakers must be conversation participants"
            )

        if len(self.messages) > self.turn_count:
            raise ValueError("number of messages must not exceed turn_count")

        if (
            self.status == "completed"
            and len(self.messages) != self.turn_count
        ):
            raise ValueError(
                "completed conversations must contain turn_count messages"
            )

        return self
