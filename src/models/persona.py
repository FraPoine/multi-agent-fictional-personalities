"""Schema for character persona JSON documents."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StrictStr, StringConstraints


NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]


class Persona(BaseModel):
    """A validated fictional-character persona."""

    model_config = ConfigDict(extra="forbid")

    character_id: NonEmptyStr
    display_name: NonEmptyStr
    description: StrictStr
    speaking_style: list[StrictStr]
    reasoning_style: list[StrictStr]
    personality_traits: list[StrictStr]
    behavior_rules: list[StrictStr]
    example_messages: list[StrictStr]
