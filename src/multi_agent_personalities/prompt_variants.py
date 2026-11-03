"""Small immutable prompt registry and source-template fingerprints."""

from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Literal

PromptVariant = Literal["baseline_v1", "dialogue_v2"]
PROMPT_DIRECTORY = Path(__file__).resolve().parents[2] / "prompts"
# Ordering is part of the fingerprint format. Paths are relative to prompts/.
PROMPT_SOURCES = MappingProxyType({
    "baseline_v1": ("agent_system_prompt.j2", "agent_reply.md"),
    "dialogue_v2": (
        "agent_system_prompt.j2",
        "conversation/dialogue_policy_v2.md",
        "conversation/dialogue_turn_v2.md",
    ),
})


def validate_prompt_variant(value: str) -> None:
    if not isinstance(value, str) or value not in PROMPT_SOURCES:
        raise ValueError(f"unsupported prompt_variant: {value!r}")


def prompt_template_sha256(
    variant: str, template_directory: Path = PROMPT_DIRECTORY,
) -> str:
    """Hash ordered UTF-8 path names and raw source bytes with length framing."""
    validate_prompt_variant(variant)
    digest = sha256()
    for name in PROMPT_SOURCES[variant]:
        for data in (name.encode("utf-8"), (template_directory / name).read_bytes()):
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
    return digest.hexdigest()
