"""Orchestration for the deterministic multi-character mock pipeline."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from multi_agent_personalities.agent_runtime import (
    build_system_prompt,
    generate_reply,
)
from multi_agent_personalities.artifacts import save_single_agent_run
from multi_agent_personalities.llm import MockProvider
from multi_agent_personalities.persona_extraction import (
    extract_persona,
    prepare_persona_prompt,
)


@dataclass(frozen=True)
class CharacterConfig:
    """Character-specific inputs for the shared pipeline."""

    slug: str
    character_id: str
    display_name: str
    description: str
    corpus_paths: tuple[Path, ...]
    persona_fixture: Path
    agent_response_fixture: Path


def character_registry(project_root: Path) -> dict[str, CharacterConfig]:
    """Build the supported-character registry relative to the repository."""

    fixture_directory = project_root / "tests" / "fixtures"
    return {
        "poirot": CharacterConfig(
            slug="poirot",
            character_id="hercule_poirot",
            display_name="Hercule Poirot",
            description=(
                "A fictional Belgian private detective known for psychological "
                "insight, method and order, attention to detail, politeness, "
                "confidence, vanity, and frequent French expressions."
            ),
            corpus_paths=(
                project_root
                / "characters"
                / "poirot"
                / "corpus"
                / "persona_corpus.jsonl",
            ),
            persona_fixture=fixture_directory / "poirot_persona_response.json",
            agent_response_fixture=fixture_directory
            / "poirot_agent_response.txt",
        ),
        "sherlock": CharacterConfig(
            slug="sherlock",
            character_id="sherlock_holmes",
            display_name="Sherlock Holmes",
            description=(
                "A fictional consulting detective known for acute observation, "
                "deductive reasoning, scientific habits, confidence, emotional "
                "reserve, and concise explanations of seemingly hidden facts."
            ),
            corpus_paths=(
                project_root
                / "characters"
                / "sherlock"
                / "corpus"
                / "persona_corpus.jsonl",
            ),
            persona_fixture=fixture_directory
            / "sherlock_persona_response.json",
            agent_response_fixture=fixture_directory
            / "sherlock_agent_response.txt",
        ),
    }


@dataclass(frozen=True)
class PipelinePaths:
    """Resolved local inputs used by one configured mock pipeline."""

    character: CharacterConfig
    corpus_paths: tuple[Path, ...]
    extraction_prompt: Path
    system_prompt_directory: Path
    persona_fixture: Path
    agent_response_fixture: Path


def default_pipeline_paths(
    project_root: Path,
    character: str = "poirot",
) -> PipelinePaths:
    """Resolve repository inputs without depending on the working directory."""

    registry = character_registry(project_root)
    if character not in registry:
        supported = ", ".join(registry)
        raise ValueError(
            f"Unsupported character: {character!r}. Supported: {supported}"
        )
    config = registry[character]
    return PipelinePaths(
        character=config,
        corpus_paths=config.corpus_paths,
        extraction_prompt=project_root / "prompts" / "extract_persona.md",
        system_prompt_directory=project_root / "prompts",
        persona_fixture=config.persona_fixture,
        agent_response_fixture=config.agent_response_fixture,
    )


def _validate_provider(provider: str) -> None:
    if provider != "mock":
        raise ValueError(
            f"Unsupported provider: {provider!r}. Supported: mock"
        )


def _require_fixture(path: Path, description: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{description} fixture not found: {path}")


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

    _validate_provider(provider_name)
    character_config = paths.character
    if character != character_config.slug:
        raise ValueError(
            "Selected character does not match the supplied character config"
        )
    if not user_message.strip():
        raise ValueError("User message cannot be empty")

    _require_fixture(paths.persona_fixture, "Mock persona response")
    _require_fixture(paths.agent_response_fixture, "Mock agent response")

    extraction_prompt, _ = prepare_persona_prompt(
        corpus_path=paths.corpus_paths,
        prompt_template_path=paths.extraction_prompt,
        character_name=character_config.display_name,
        character_description=character_config.description,
    )
    mock_provider = MockProvider(
        {
            "persona_extraction": paths.persona_fixture,
            "agent_reply": paths.agent_response_fixture,
        }
    )
    persona = extract_persona(mock_provider, extraction_prompt)
    if (
        persona.character_id != character_config.character_id
        or persona.display_name != character_config.display_name
    ):
        raise ValueError(
            "Mock persona identity does not match the selected character"
        )

    created_at = timestamp or datetime.now(timezone.utc)
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    created_at_utc = created_at.astimezone(timezone.utc)
    run_id = created_at_utc.strftime("%Y%m%dT%H%M%S.%fZ")

    system_prompt = build_system_prompt(
        persona,
        paths.system_prompt_directory,
    )
    response = generate_reply(
        persona=persona,
        history=[],
        topic=user_message,
        run_id=run_id,
        turn_index=0,
        provider=mock_provider,
        provider_name=provider_name,
        model_name="mock",
        timestamp=created_at_utc,
    )

    return save_single_agent_run(
        output_root=output_root,
        character_slug=character,
        run_id=run_id,
        created_at=created_at_utc,
        persona=persona,
        system_prompt=system_prompt,
        response=response,
        user_message=user_message,
        is_synthetic=True,
    )
