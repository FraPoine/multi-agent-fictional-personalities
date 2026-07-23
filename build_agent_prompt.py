import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


# This script is stored in the repository root, so its direct parent is the
# project root. parents[1] would incorrectly select the directory above it.
PROJECT_ROOT = Path(__file__).resolve().parent

PERSONA_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "sherlock"
    / "sherlock_persona_generated.json"
)

TEMPLATE_DIRECTORY = PROJECT_ROOT / "prompts"
TEMPLATE_FILENAME = "agent_system_prompt.j2"

OUTPUT_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "sherlock"
    / "sherlock_system_prompt.txt"
)


REQUIRED_FIELDS = {
    "character_id",
    "display_name",
    "description",
    "speaking_style",
    "reasoning_style",
    "personality_traits",
    "behavior_rules",
    "example_messages",
}


def load_persona(path: Path) -> dict:
    """Load and validate the persona JSON."""

    if not path.exists():
        raise FileNotFoundError(
            f"Persona file not found: {path}"
        )

    try:
        persona = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid persona JSON: {error}"
        ) from error

    missing_fields = REQUIRED_FIELDS - persona.keys()

    if missing_fields:
        raise ValueError(
            f"Missing persona fields: {sorted(missing_fields)}"
        )

    return persona


def create_environment() -> Environment:
    """Create the Jinja2 environment."""

    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIRECTORY)),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_system_prompt(persona: dict) -> str:
    """Render the system prompt using the persona data."""

    environment = create_environment()
    template = environment.get_template(TEMPLATE_FILENAME)

    return template.render(**persona).strip() + "\n"


def main() -> None:
    persona = load_persona(PERSONA_PATH)
    system_prompt = build_system_prompt(persona)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        system_prompt,
        encoding="utf-8",
    )

    print(f"Character: {persona['display_name']}")
    print(f"System prompt saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
    
