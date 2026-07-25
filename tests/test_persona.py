"""Tests for the reusable persona schema."""

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models.persona import Persona


@pytest.fixture
def valid_persona() -> dict:
    return {
        "character_id": "sherlock_holmes",
        "display_name": "Sherlock Holmes",
        "description": "A consulting detective.",
        "speaking_style": ["Precise"],
        "reasoning_style": ["Deductive"],
        "personality_traits": ["Observant"],
        "behavior_rules": ["Explain conclusions"],
        "example_messages": ["You see, but you do not observe."],
    }


def test_valid_persona(valid_persona: dict) -> None:
    persona = Persona.model_validate(valid_persona)

    assert persona.character_id == "sherlock_holmes"


def test_missing_field_is_rejected(valid_persona: dict) -> None:
    del valid_persona["description"]

    with pytest.raises(ValidationError):
        Persona.model_validate(valid_persona)


def test_unexpected_field_is_rejected(valid_persona: dict) -> None:
    valid_persona["unexpected"] = "value"

    with pytest.raises(ValidationError):
        Persona.model_validate(valid_persona)


def test_invalid_list_field_is_rejected(valid_persona: dict) -> None:
    valid_persona["speaking_style"] = "Precise"

    with pytest.raises(ValidationError):
        Persona.model_validate(valid_persona)
