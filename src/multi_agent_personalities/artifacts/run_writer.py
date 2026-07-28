"""Persistence for generated agent responses and execution metadata."""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def save_agent_run(
    *,
    output_root: Path,
    character_id: str,
    response_text: str,
    provider_name: str,
    model_name: str,
    is_synthetic: bool,
    run_id: str | None = None,
    created_at: datetime | None = None,
) -> Path:
    """Save one agent response and its metadata in a new run directory."""

    required_values = {
        "character_id": character_id,
        "response_text": response_text,
        "provider_name": provider_name,
        "model_name": model_name,
    }
    for field_name, value in required_values.items():
        if not value.strip():
            raise ValueError(f"{field_name} cannot be empty")

    if run_id is not None and not run_id.strip():
        raise ValueError("run_id cannot be empty")

    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")

    resolved_run_id = run_id or uuid4().hex
    run_directory = (
        Path(output_root)
        / character_id
        / "runs"
        / resolved_run_id
    )
    run_directory.mkdir(parents=True, exist_ok=False)

    response_filename = "response.txt"
    (run_directory / response_filename).write_text(
        response_text,
        encoding="utf-8",
    )

    metadata = {
        "run_id": resolved_run_id,
        "created_at": timestamp.isoformat(),
        "character_id": character_id,
        "task_name": "agent_reply",
        "provider": provider_name,
        "model": model_name,
        "is_synthetic": is_synthetic,
        "response_file": response_filename,
    }
    (run_directory / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return run_directory
