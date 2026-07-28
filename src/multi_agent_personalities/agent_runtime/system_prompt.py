"""Build agent system prompts from validated personas."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from multi_agent_personalities.models.persona import Persona


def build_system_prompt(
    persona: Persona,
    template_directory: Path,
    template_filename: str = "agent_system_prompt.j2",
) -> str:
    """Render a system prompt for a validated persona."""

    if not template_directory.is_dir():
        raise FileNotFoundError(
            f"System prompt template directory not found: {template_directory}"
        )

    template_path = template_directory / template_filename
    if not template_path.is_file():
        raise FileNotFoundError(
            f"System prompt template file not found: {template_path}"
        )

    environment = Environment(
        loader=FileSystemLoader(str(template_directory)),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template(template_filename)

    return template.render(**persona.model_dump()).strip() + "\n"
