"""Application orchestration for the complete technical evaluation pilot."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets

from multi_agent_personalities.application.conversation_service import run_mock_conversation
from multi_agent_personalities.evaluation.config import load_pilot_config
from multi_agent_personalities.evaluation.persistence import save_pilot
from multi_agent_personalities.evaluation.trials import build_trials


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
) -> PilotPreparationResult:
    """Generate mock source runs and atomically publish six blind trials."""
    config = load_pilot_config(config_path)
    identifier = pilot_id or _new_pilot_id()
    pilot_target = Path(output_root) / "evaluation" / "pilots" / identifier
    if pilot_target.exists():
        raise FileExistsError(f"pilot already exists: {pilot_target}")
    results = []
    for index, topic in enumerate(config.topics, start=1):
        results.append(run_mock_conversation(
            character_slugs=config.characters,
            topic=topic,
            turn_count=config.turns_per_conversation,
            seed=config.seed,
            output_root=output_root,
            project_root=project_root,
            run_id=f"{identifier}_source_{index}",
        ))
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
        "config_path": str(Path(config_path).relative_to(project_root)),
        "configuration": config.model_dump(mode="json"),
        "source_run_ids": [item.run_id for item in results],
        "source_run_directories": [str(item.artifact_directory) for item in results],
        "trial_count": len(built.trials),
        "trial_generation": built.summary,
    }
    directory = save_pilot(output_root=output_root, pilot_id=identifier, trials=built.trials, manifest=manifest)
    return PilotPreparationResult(identifier, directory, tuple(item.run_id for item in results))
