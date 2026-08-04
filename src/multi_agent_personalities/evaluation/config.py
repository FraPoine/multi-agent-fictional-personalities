"""Versioned technical-pilot configuration loading."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class PilotConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    characters: tuple[Literal["sherlock", "poirot"], Literal["sherlock", "poirot"]]
    topics: tuple[str, str, str]
    conversations_per_topic: Literal[1]
    turns_per_conversation: Literal[6]
    trials_per_character: Literal[3]
    intended_raters: Literal[2]
    confidence_min: Literal[1]
    confidence_max: Literal[5]
    chance_baseline: Literal[0.5]
    seed: Literal[42]
    minimum_text_length: int = Field(gt=0)
    condition: str = Field(min_length=1)


def load_pilot_config(path: Path) -> PilotConfig:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"cannot load pilot configuration: {error}") from error
    if not isinstance(data, dict) or "pilot" not in data:
        raise ValueError("pilot configuration must contain a pilot mapping")
    config = PilotConfig.model_validate(data["pilot"])
    if set(config.characters) != {"sherlock", "poirot"}:
        raise ValueError("pilot must contain Sherlock and Poirot exactly once")
    if any(not topic.strip() for topic in config.topics):
        raise ValueError("pilot topics must not be empty")
    return config
