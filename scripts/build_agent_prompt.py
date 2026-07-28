import json
from pathlib import Path

from pydantic import ValidationError

from multi_agent_personalities.agent_runtime import build_system_prompt
from multi_agent_personalities.models.persona import Persona


# This script lives under scripts/, so its parent directory's parent is the
# project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

PERSONA_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "poirot"
    / "poirot_persona_generated.json"
)

TEMPLATE_DIRECTORY = PROJECT_ROOT / "prompts"
TEMPLATE_FILENAME = "agent_system_prompt.j2"

OUTPUT_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "poirot"
    / "poirot_system_prompt.txt"
)


def load_persona(path: Path) -> Persona:
    """Load and validate the persona JSON."""

    if not path.exists():
        raise FileNotFoundError(
            f"Persona file not found: {path}"
        )

    try:
        persona_data = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid persona JSON: {error}"
        ) from error

    try:
        return Persona.model_validate(persona_data)
    except ValidationError as error:
        raise ValueError(
            f"Invalid persona data in {path}: {error}"
        ) from error


def main() -> None:
    persona = load_persona(PERSONA_PATH)
    system_prompt = build_system_prompt(
        persona,
        TEMPLATE_DIRECTORY,
        TEMPLATE_FILENAME,
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        system_prompt,
        encoding="utf-8",
    )

    print(f"Character: {persona.display_name}")
    print(f"System prompt saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
    
