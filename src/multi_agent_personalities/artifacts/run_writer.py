"""Persistence for generated agent responses and execution metadata."""

import json
from datetime import datetime
from pathlib import Path

from multi_agent_personalities.models.message import Message
from multi_agent_personalities.models.persona import Persona


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} cannot be empty")


def save_single_agent_run(
    *,
    output_root: Path,
    character_slug: str,
    run_id: str,
    created_at: datetime,
    persona: Persona,
    system_prompt: str,
    response: Message,
    user_message: str,
    is_synthetic: bool,
) -> Path:
    """Save one validated reply using the canonical run artifact format."""
    for field_name, value in {
        "character_slug": character_slug,
        "run_id": run_id,
        "system_prompt": system_prompt,
        "user_message": user_message,
    }.items():
        _require_non_empty(value, field_name)
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    if response.run_id != run_id:
        raise ValueError("response run_id must match run_id")
    if response.speaker_character_id != persona.character_id:
        raise ValueError("response character_id must match persona")
    if response.timestamp != created_at:
        raise ValueError("response timestamp must match created_at")
    _require_non_empty(response.text, "response.text")
    _require_non_empty(response.provider, "response.provider")

    run_directory = (
        Path(output_root)
        / character_slug
        / "runs"
        / run_id
    )
    run_directory.mkdir(parents=True, exist_ok=False)

    persona_filename = "persona.json"
    system_prompt_filename = "system_prompt.txt"
    response_filename = "response.txt"
    (run_directory / persona_filename).write_text(
        persona.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (run_directory / system_prompt_filename).write_text(
        system_prompt,
        encoding="utf-8",
    )
    (run_directory / response_filename).write_text(
        response.text,
        encoding="utf-8",
    )

    metadata = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "character_id": response.speaker_character_id,
        "character_slug": character_slug,
        "task_name": "agent_reply",
        "provider": response.provider,
        "model": response.model,
        "is_synthetic": is_synthetic,
        "user_message": user_message,
        "persona_file": persona_filename,
        "system_prompt_file": system_prompt_filename,
        "response_file": response_filename,
    }
    (run_directory / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return run_directory
