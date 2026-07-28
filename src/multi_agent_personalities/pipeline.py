"""Orchestration for the current single-character mock pipeline."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from multi_agent_personalities.agent_runtime import build_system_prompt
from multi_agent_personalities.llm import MockProvider
from multi_agent_personalities.persona_extraction import (
    extract_persona,
    prepare_persona_prompt,
    save_persona,
)


POIROT_DESCRIPTION = (
    "A fictional Belgian private detective known for psychological insight, "
    "method and order, attention to detail, politeness, confidence, vanity, "
    "and frequent French expressions."
)


@dataclass(frozen=True)
class PipelinePaths:
    """Local inputs used by the mock Poirot pipeline."""

    corpus: Path
    extraction_prompt: Path
    system_prompt_directory: Path
    persona_fixture: Path
    agent_response_fixture: Path


def default_pipeline_paths(project_root: Path) -> PipelinePaths:
    """Resolve repository inputs without depending on the working directory."""

    return PipelinePaths(
        corpus=(
            project_root
            / "characters"
            / "poirot"
            / "corpus"
            / "persona_corpus.jsonl"
        ),
        extraction_prompt=project_root / "prompts" / "extract_persona.md",
        system_prompt_directory=project_root / "prompts",
        persona_fixture=(
            project_root
            / "tests"
            / "fixtures"
            / "poirot_persona_response.json"
        ),
        agent_response_fixture=(
            project_root
            / "tests"
            / "fixtures"
            / "poirot_agent_response.txt"
        ),
    )


def _validate_supported(character: str, provider: str) -> None:
    if character != "poirot":
        raise ValueError(
            f"Unsupported character: {character!r}. Supported: poirot"
        )
    if provider != "mock":
        raise ValueError(
            f"Unsupported provider: {provider!r}. Supported: mock"
        )


def _require_fixture(path: Path, description: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{description} fixture not found: {path}")


def _new_run_directory(
    output_root: Path,
    character: str,
    timestamp: datetime,
) -> tuple[str, Path]:
    run_id = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    run_directory = output_root / character / "runs" / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    return run_id, run_directory


def _build_agent_prompt(system_prompt: str, user_message: str) -> str:
    return (
        f"{system_prompt.rstrip()}\n\n"
        "## User message\n\n"
        f"{user_message.strip()}\n"
    )


def run_pipeline(
    *,
    character: str,
    provider_name: str,
    user_message: str,
    output_root: Path,
    paths: PipelinePaths,
    timestamp: datetime | None = None,
) -> Path:
    """Run persona extraction and one agent reply using local mock fixtures."""

    _validate_supported(character, provider_name)
    if not user_message.strip():
        raise ValueError("User message cannot be empty")

    _require_fixture(paths.persona_fixture, "Mock persona response")
    _require_fixture(paths.agent_response_fixture, "Mock agent response")

    extraction_prompt, _ = prepare_persona_prompt(
        corpus_path=paths.corpus,
        prompt_template_path=paths.extraction_prompt,
        character_name="Hercule Poirot",
        character_description=POIROT_DESCRIPTION,
    )
    mock_provider = MockProvider(
        {
            "persona_extraction": paths.persona_fixture,
            "agent_reply": paths.agent_response_fixture,
        }
    )
    persona = extract_persona(mock_provider, extraction_prompt)

    created_at = timestamp or datetime.now(timezone.utc)
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    created_at_utc = created_at.astimezone(timezone.utc)
    run_id, run_directory = _new_run_directory(
        output_root,
        character,
        created_at_utc,
    )

    persona_path = save_persona(persona, run_directory / "persona.json")
    system_prompt = build_system_prompt(
        persona,
        paths.system_prompt_directory,
    )
    agent_prompt = _build_agent_prompt(system_prompt, user_message)
    response = mock_provider.generate(
        agent_prompt,
        task_name="agent_reply",
    )

    system_prompt_path = run_directory / "system_prompt.txt"
    response_path = run_directory / "response.txt"
    metadata_path = run_directory / "metadata.json"
    system_prompt_path.write_text(system_prompt, encoding="utf-8")
    response_path.write_text(response, encoding="utf-8")

    metadata = {
        "run_id": run_id,
        "timestamp_utc": created_at_utc.isoformat(),
        "character": character,
        "provider": provider_name,
        "model": "mock",
        "is_synthetic": True,
        "user_message": user_message,
        "persona_path": persona_path.name,
        "system_prompt_path": system_prompt_path.name,
        "response_path": response_path.name,
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return run_directory
