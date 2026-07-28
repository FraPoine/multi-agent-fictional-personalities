"""Tests for reusable agent system-prompt construction."""

from pathlib import Path

import pytest

from multi_agent_personalities.agent_runtime import build_system_prompt
from multi_agent_personalities.models.persona import Persona


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIRECTORY = PROJECT_ROOT / "prompts"


@pytest.fixture
def generic_persona() -> Persona:
    return Persona.model_validate(
        {
            "character_id": "generic_test_character",
            "display_name": "Morgan Vale",
            "description": "A fictional investigator used for testing.",
            "speaking_style": ["Uses concise, measured sentences"],
            "reasoning_style": ["Compares competing explanations"],
            "personality_traits": ["Patient"],
            "behavior_rules": ["State uncertainty explicitly"],
            "example_messages": ["Let us examine what the evidence supports."],
        }
    )


def test_builds_prompt_from_generic_persona(
    generic_persona: Persona,
) -> None:
    prompt = build_system_prompt(generic_persona, TEMPLATE_DIRECTORY)

    assert prompt
    assert generic_persona.display_name in prompt
    assert generic_persona.speaking_style[0] in prompt
    assert generic_persona.reasoning_style[0] in prompt
    assert generic_persona.behavior_rules[0] in prompt
    assert "Poirot" not in prompt


def test_prompt_ends_with_exactly_one_newline(
    generic_persona: Persona,
) -> None:
    prompt = build_system_prompt(generic_persona, TEMPLATE_DIRECTORY)

    assert prompt.endswith("\n")
    assert not prompt.endswith("\n\n")


def test_missing_template_file_raises_clear_error(
    tmp_path: Path,
    generic_persona: Persona,
) -> None:
    with pytest.raises(
        FileNotFoundError,
        match="System prompt template file not found",
    ):
        build_system_prompt(
            generic_persona,
            tmp_path,
            "missing_template.j2",
        )


def test_missing_template_directory_raises_clear_error(
    tmp_path: Path,
    generic_persona: Persona,
) -> None:
    missing_directory = tmp_path / "missing"

    with pytest.raises(
        FileNotFoundError,
        match="System prompt template directory not found",
    ):
        build_system_prompt(generic_persona, missing_directory)
