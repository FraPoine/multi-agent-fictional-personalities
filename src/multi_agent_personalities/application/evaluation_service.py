"""Application orchestration for the complete technical evaluation pilot."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import secrets
import shutil
from collections.abc import Callable

from multi_agent_personalities.application.conversation_service import run_mock_conversation
from multi_agent_personalities.evaluation.config import load_pilot_config
from multi_agent_personalities.evaluation.persistence import save_pilot
from multi_agent_personalities.evaluation.trials import build_trials
from multi_agent_personalities.models.identifiers import validate_run_id


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "evaluation_pilot.yaml"


@dataclass(frozen=True)
class PilotPreparationResult:
    pilot_id: str
    pilot_directory: Path
    source_run_ids: tuple[str, ...]


def _new_pilot_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"pilot_{stamp}_{secrets.token_hex(4)}"


def prepare_technical_pilot(
    *, output_root: Path = Path("outputs"), project_root: Path = PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG, pilot_id: str | None = None,
    _run_conversation: Callable[..., object] = run_mock_conversation,
    _save_pilot: Callable[..., Path] = save_pilot,
) -> PilotPreparationResult:
    """Generate mock source runs and atomically publish six blind trials."""
    resolved_project_root = Path(project_root).resolve()
    resolved_config = Path(config_path).resolve()
    try:
        config_label = resolved_config.relative_to(resolved_project_root).as_posix()
    except ValueError as error:
        raise ValueError("pilot configuration must be inside the project root") from error
    config = load_pilot_config(resolved_config)
    identifier = pilot_id or _new_pilot_id()
    validate_run_id(identifier)
    pilot_target = Path(output_root) / "evaluation" / "pilots" / identifier
    if pilot_target.exists():
        raise FileExistsError(f"pilot already exists: {pilot_target}")
    source_ids = tuple(
        f"{identifier}_source_{index}" for index in range(1, len(config.topics) + 1)
    )
    source_paths = tuple(
        Path(output_root) / "conversations" / "runs" / run_id
        for run_id in source_ids
    )
    existing = [path for path in source_paths if path.exists()]
    if existing:
        raise FileExistsError("one or more pilot source run IDs already exist")

    results = []
    created_paths: list[Path] = []
    try:
        for topic, run_id in zip(config.topics, source_ids):
            result = _run_conversation(
                character_slugs=config.characters,
                topic=topic,
                turn_count=config.turns_per_conversation,
                seed=config.seed,
                output_root=output_root,
                project_root=resolved_project_root,
                run_id=run_id,
            )
            results.append(result)
            created_paths.append(result.artifact_directory)
        built = build_trials(
            [item.run for item in results],
            trials_per_character=config.trials_per_character,
            seed=config.seed,
            minimum_text_length=config.minimum_text_length,
            condition=config.condition,
        )
        manifest = {
            "pilot_id": identifier,
            "status": "completed",
            "technical_mock_pilot": True,
            "synthetic_data": True,
            "synthetic_responses_created": False,
            "config_path": config_label,
            "configuration": config.model_dump(mode="json"),
            "source_run_ids": [item.run_id for item in results],
            "source_run_directories": [str(item.artifact_directory) for item in results],
            "trial_count": len(built.trials),
            "trial_generation": built.summary,
        }
        directory = _save_pilot(
            output_root=output_root,
            pilot_id=identifier,
            trials=built.trials,
            manifest=manifest,
        )
    except BaseException:
        for path in created_paths:
            if path.exists():
                shutil.rmtree(path)
        raise
    return PilotPreparationResult(identifier, directory, source_ids)
