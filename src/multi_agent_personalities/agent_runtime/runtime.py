"""Generate one validated in-character conversation message."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from multi_agent_personalities.agent_runtime.system_prompt import (
    build_system_prompt,
)
from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.models.message import Message
from multi_agent_personalities.models.persona import Persona


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PROMPT_DIRECTORY = _PROJECT_ROOT / "prompts"
_REPLY_PROMPT_PATH = _PROMPT_DIRECTORY / "agent_reply.md"


def _require_non_empty(value: str, field_name: str) -> None:
    """Require a non-empty string for a runtime identifier or topic."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _validate_history(
    history: Sequence[Message],
    *,
    run_id: str,
    turn_index: int,
) -> None:
    """Require every previous turn exactly once in chronological order."""
    for message in history:
        if message.run_id != run_id:
            raise ValueError(
                "history messages must belong to the requested run_id"
            )

    actual_indexes = [message.turn_index for message in history]
    if len(actual_indexes) != len(set(actual_indexes)):
        raise ValueError("history contains duplicate turn indexes")

    expected_indexes = list(range(turn_index))
    if actual_indexes != expected_indexes:
        raise ValueError(
            "history must contain every previous turn in chronological order"
        )


def _format_history(history: Sequence[Message]) -> str:
    """Format ordered history without changing its text or supplied order."""
    if not history:
        return "No previous messages."
    return "\n".join(
        f"[Turn {message.turn_index}] {message.speaker_name}: {message.text}"
        for message in history
    )


def _build_reply_prompt(
    *,
    persona: Persona,
    topic: str,
    history: Sequence[Message],
) -> str:
    """Resolve the versioned reply prompt using existing persona rendering."""
    if not _REPLY_PROMPT_PATH.is_file():
        raise FileNotFoundError(
            f"Agent reply prompt file not found: {_REPLY_PROMPT_PATH}"
        )

    template = _REPLY_PROMPT_PATH.read_text(encoding="utf-8")
    replacements = {
        "{persona_profile}": build_system_prompt(
            persona,
            _PROMPT_DIRECTORY,
        ).strip(),
        "{topic}": topic,
        "{conversation_history}": _format_history(history),
    }
    prompt = template
    for placeholder, value in replacements.items():
        if placeholder not in prompt:
            raise ValueError(
                f"Missing placeholder in agent reply prompt: {placeholder}"
            )
        prompt = prompt.replace(placeholder, value)
    return prompt.strip() + "\n"


def generate_reply(
    *,
    persona: Persona,
    history: Sequence[Message],
    topic: str,
    run_id: str,
    turn_index: int,
    provider: LLMProvider,
    provider_name: str,
    model_name: str | None = None,
    timestamp: datetime | None = None,
) -> Message:
    """Generate exactly one message for a caller-selected persona and turn."""
    _require_non_empty(topic, "topic")
    _require_non_empty(run_id, "run_id")
    _require_non_empty(provider_name, "provider_name")
    if turn_index < 0:
        raise ValueError("turn_index must be greater than or equal to zero")
    _validate_history(history, run_id=run_id, turn_index=turn_index)

    created_at = timestamp or datetime.now(timezone.utc)
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")

    resolved_prompt = _build_reply_prompt(
        persona=persona,
        topic=topic,
        history=history,
    )
    result = provider.generate(
        resolved_prompt,
        task_name="agent_reply",
    )
    if provider_name != result.metadata.provider:
        raise ValueError(
            "declared provider does not match generation metadata provider"
        )
    reported_model = result.metadata.model
    if (
        reported_model is not None
        and model_name is not None
        and reported_model != model_name
    ):
        raise ValueError(
            "declared model does not match generation metadata model"
        )
    resolved_model = reported_model if reported_model is not None else model_name

    return Message(
        message_id=f"{run_id}_message_{turn_index:04d}",
        run_id=run_id,
        turn_index=turn_index,
        speaker_character_id=persona.character_id,
        speaker_name=persona.display_name,
        text=result.text,
        provider=result.metadata.provider,
        model=resolved_model,
        generation_metadata=result.metadata,
        timestamp=created_at,
        error=None,
    )
