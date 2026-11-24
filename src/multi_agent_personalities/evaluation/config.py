"""Versioned technical-pilot configuration loading."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class BenchmarkPersona(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class BenchmarkScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^scenario_0[1-6]$")
    title: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    speaker_order: tuple[str, str, str]


class ThreePersonaBenchmarkConfig(BaseModel):
    """Fixed development protocol, separate from the historical mock pilot."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    id: Literal["three_personas_v1"]
    status: Literal["development_pilot"]
    characters: tuple[Literal["sherlock"], Literal["poirot"], Literal["layton"]]
    provider: Literal["copilot"]
    model: str = Field(strict=True, min_length=1)
    prompt_variant: Literal["dialogue_v2"]
    prompt_template_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conversations_per_scenario: Literal[1]
    turns_per_conversation: Literal[6]
    selected_messages_per_character_per_scenario: Literal[1]
    intended_raters: Literal[3]
    confidence_min: Literal[1]
    confidence_max: Literal[5]
    chance_baseline: Literal[1 / 3]
    seed: Literal[42]
    primary_metric: Literal["blind_character_identification_accuracy"]
    personas: dict[str, BenchmarkPersona]
    scenarios: tuple[BenchmarkScenario, ...] = Field(min_length=6, max_length=6)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("model must be an explicit nonempty identifier")
        return value


def load_three_persona_benchmark_config(path: Path) -> ThreePersonaBenchmarkConfig:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"cannot load benchmark configuration: {error}") from error
    if not isinstance(data, dict) or set(data) != {"benchmark"}:
        raise ValueError("benchmark configuration must contain only a benchmark mapping")
    config = ThreePersonaBenchmarkConfig.model_validate(data["benchmark"])
    if set(config.personas) != set(config.characters):
        raise ValueError("benchmark must specify all three personas")
    for index, scenario in enumerate(config.scenarios):
        if scenario.id != f"scenario_{index + 1:02}":
            raise ValueError("scenarios must be in canonical order")
        order = config.characters[index % 3:] + config.characters[:index % 3]
        if scenario.speaker_order != order:
            raise ValueError("scenario speaker order must follow the fixed rotation")
        if not scenario.topic.strip() or not scenario.title.strip():
            raise ValueError("scenario title and topic must not be blank")
    if len({item.topic for item in config.scenarios}) != 6:
        raise ValueError("scenario topics must be distinct")
    return config
