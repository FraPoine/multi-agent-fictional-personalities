"""Generate and validate character personas."""

from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.models.persona import Persona


def extract_persona(
    provider: LLMProvider,
    prompt: str,
) -> Persona:
    """Generate and validate a persona from a persona-extraction prompt."""

    raw_output = provider.generate(
        prompt,
        task_name="persona_extraction",
    )

    return Persona.model_validate_json(raw_output)
