"""Application orchestration for deterministic mock conversations."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from multi_agent_personalities.artifacts import save_conversation_run
from multi_agent_personalities.llm import MockProvider
from multi_agent_personalities.models import (
    ConversationRun,
    Persona,
    validate_run_id,
)
from multi_agent_personalities.pipeline import character_registry
from multi_agent_personalities.simulation import (
    ConversationParticipant,
    simulate_chat,
)


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ARTIFACT_FILENAMES = ("run.json", "messages.jsonl", "transcript.md")
_SaveConversationRun = Callable[..., Path]


@dataclass(frozen=True)
class ConversationResult:
    """A completed conversation and the directory containing its artifacts."""

    run: ConversationRun
    artifact_directory: Path

    @property
    def run_id(self) -> str:
        """Return the validated run identifier."""
        return self.run.run_id

    @property
    def artifact_paths(self) -> tuple[Path, ...]:
        """Return the three canonical conversation artifact paths."""
        return tuple(
            self.artifact_directory / filename
            for filename in _ARTIFACT_FILENAMES
        )

    @property
    def transcript_path(self) -> Path:
        """Return the human-readable transcript path."""
        return self.artifact_directory / "transcript.md"


def _load_mock_participants(
    character_slugs: Sequence[str],
    project_root: Path,
) -> list[ConversationParticipant]:
    if isinstance(character_slugs, (str, bytes)) or not isinstance(
        character_slugs, Sequence
    ):
        raise ValueError("character_slugs must be a sequence of strings")
    if any(not isinstance(slug, str) for slug in character_slugs):
        raise ValueError("character_slugs must contain only strings")
    if len(character_slugs) < 2:
        raise ValueError("at least two characters are required")
    if len(character_slugs) != len(set(character_slugs)):
        raise ValueError("characters must not contain duplicates")

    registry = character_registry(project_root)
    unsupported = [slug for slug in character_slugs if slug not in registry]
    if unsupported:
        supported = ", ".join(registry)
        raise ValueError(
            f"unsupported character: {unsupported[0]!r}. Supported: {supported}"
        )

    participants: list[ConversationParticipant] = []
    for slug in character_slugs:
        config = registry[slug]
        try:
            persona = Persona.model_validate_json(
                config.persona_fixture.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as error:
            raise ValueError(
                f"invalid synthetic persona fixture for {slug!r}: {error}"
            ) from error
        if (persona.character_id, persona.display_name) != (
            config.character_id,
            config.display_name,
        ):
            raise ValueError(
                f"synthetic persona identity does not match {slug!r}"
            )

        try:
            response = config.agent_response_fixture.read_text(encoding="utf-8")
        except OSError as error:
            raise ValueError(
                f"invalid synthetic response fixture for {slug!r}: {error}"
            ) from error
        if not response.strip():
            raise ValueError(f"synthetic response fixture for {slug!r} is empty")

        participants.append(
            ConversationParticipant(
                persona=persona,
                provider=MockProvider(
                    {"agent_reply": config.agent_response_fixture}
                ),
                provider_name="mock",
                model_name="mock-round-robin",
            )
        )

    return participants


def run_mock_conversation(
    *,
    character_slugs: Sequence[str],
    topic: str,
    turn_count: int,
    seed: int = 42,
    output_root: Path = Path("outputs"),
    project_root: Path | None = None,
    run_id: str | None = None,
    timestamp: datetime | None = None,
    _save_run: _SaveConversationRun = save_conversation_run,
) -> ConversationResult:
    """Run and persist one deterministic local mock conversation."""
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("topic must not be empty")
    if isinstance(turn_count, bool) or not isinstance(turn_count, int):
        raise ValueError("turn_count must be a positive integer")
    if turn_count <= 0:
        raise ValueError("turn_count must be greater than zero")
    if run_id is not None:
        validate_run_id(run_id)

    resolved_project_root = (
        _PROJECT_ROOT if project_root is None else Path(project_root)
    )
    participants = _load_mock_participants(
        character_slugs,
        resolved_project_root,
    )
    run = simulate_chat(
        participants=participants,
        topic=topic,
        turn_count=turn_count,
        seed=seed,
        run_id=run_id,
        timestamp=timestamp,
    )
    artifact_directory = _save_run(output_root=Path(output_root), run=run)
    return ConversationResult(
        run=run,
        artifact_directory=artifact_directory,
    )
