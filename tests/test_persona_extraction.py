"""Tests for persona extraction using deterministic synthetic mock output."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from multi_agent_personalities.llm import MockProvider
from multi_agent_personalities.models.persona import Persona
from multi_agent_personalities.persona_extraction import extract_persona


def test_extracts_valid_persona_from_mock_output() -> None:
    fixture_path = (
        Path(__file__).parent / "fixtures" / "poirot_persona_response.json"
    )
    provider = MockProvider({"persona_extraction": fixture_path})

    persona = extract_persona(
        provider,
        "Extract Hercule Poirot's persona.",
    )

    assert isinstance(persona, Persona)
    assert persona.character_id == "hercule_poirot"
    assert persona.display_name == "Hercule Poirot"


def test_rejects_mock_output_with_invalid_schema(tmp_path: Path) -> None:
    response_file = tmp_path / "missing_required_field.json"
    response_file.write_text(
        '{"character_id": "hercule_poirot"}',
        encoding="utf-8",
    )
    provider = MockProvider({"persona_extraction": response_file})

    with pytest.raises(ValidationError):
        extract_persona(provider, "Extract the persona.")


def test_rejects_malformed_mock_json(tmp_path: Path) -> None:
    response_file = tmp_path / "malformed.json"
    response_file.write_text(
        '{"character_id": "hercule_poirot"',
        encoding="utf-8",
    )
    provider = MockProvider({"persona_extraction": response_file})

    with pytest.raises(ValidationError):
        extract_persona(provider, "Extract the persona.")
