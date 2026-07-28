"""Persistence helpers for validated personas."""

import json
from pathlib import Path

from multi_agent_personalities.models.persona import Persona


def save_persona(
    persona: Persona,
    output_path: Path,
) -> Path:
    """Save a validated persona as readable UTF-8 JSON."""

    resolved_path = output_path.resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(
        json.dumps(persona.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return resolved_path
