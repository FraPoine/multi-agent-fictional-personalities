"""Tests for persona JSON persistence."""

import json
from pathlib import Path

import pytest

from multi_agent_personalities.models.persona import Persona
from multi_agent_personalities.persona_extraction import save_persona


@pytest.fixture
def persona() -> Persona:
    return Persona.model_validate(
        {
            "character_id": "hercule_poirot",
            "display_name": "Hercule Poirot",
            "description": "A Belgian détective.",
            "speaking_style": ["Précis", "Courteous"],
            "reasoning_style": ["Methodical"],
            "personality_traits": ["Méticuleux"],
            "behavior_rules": ["Use the little grey cells"],
            "example_messages": ["Mon ami, voilà la solution."],
        }
    )


def test_save_persona_creates_file_and_parent_directories(
    tmp_path: Path,
    persona: Persona,
) -> None:
    output_path = tmp_path / "nested" / "run" / "persona.json"

    saved_path = save_persona(persona, output_path)

    assert output_path.is_file()
    assert output_path.parent.is_dir()
    assert saved_path == output_path.resolve()
    assert saved_path.is_file()


def test_saved_json_matches_persona_and_preserves_non_ascii(
    tmp_path: Path,
    persona: Persona,
) -> None:
    output_path = tmp_path / "persona.json"

    save_persona(persona, output_path)

    saved_text = output_path.read_text(encoding="utf-8")
    assert json.loads(saved_text) == persona.model_dump()
    assert "détective" in saved_text
    assert "Méticuleux" in saved_text
    assert "\\u00e9" not in saved_text
    assert saved_text.endswith("\n")


def test_saved_json_can_be_validated_again(
    tmp_path: Path,
    persona: Persona,
) -> None:
    saved_path = save_persona(persona, tmp_path / "persona.json")

    loaded_persona = Persona.model_validate_json(
        saved_path.read_text(encoding="utf-8")
    )

    assert loaded_persona == persona
