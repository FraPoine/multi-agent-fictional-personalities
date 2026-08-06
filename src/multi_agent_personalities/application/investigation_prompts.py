"""Versioned prompt loading and deterministic investigation context rendering."""

import re
from collections.abc import Mapping, Sequence
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from multi_agent_personalities.agent_runtime import build_system_prompt
from multi_agent_personalities.models import (
    AgentAnalysis,
    EvidenceReference,
    GroupDecision,
    Hypothesis,
    InvestigationSession,
    Message,
    Persona,
)


SUPPORTED_PROMPT_VERSION = 1
_PROMPT_DIRECTORY = Path(__file__).resolve().parents[3] / "prompts"
_VERSION_PATTERN = re.compile(r"Prompt-Version: ([1-9][0-9]*)\Z")
_PLACEHOLDER_PATTERN = re.compile(r"{{([a-z][a-z0-9_]*)}}")


class InvestigationPromptError(ValueError):
    """Raised when an investigation prompt contract cannot be satisfied."""


class InvestigationPromptName(str, Enum):
    """Fixed names of supported investigation prompt templates."""

    ANALYSIS = "analysis"
    DISCUSSION = "discussion"
    DECISION = "decision"
    FINAL_THEORY = "final_theory"


_PROMPT_FILES = {
    InvestigationPromptName.ANALYSIS: "investigation_analysis.md",
    InvestigationPromptName.DISCUSSION: "investigation_discussion.md",
    InvestigationPromptName.DECISION: "investigation_decision.md",
    InvestigationPromptName.FINAL_THEORY: "investigation_final_theory.md",
}

_REQUIRED_PLACEHOLDERS = {
    InvestigationPromptName.ANALYSIS: (
        "session_id",
        "round_id",
        "case_introduction",
        "participant_id",
        "persona_profile",
        "visible_clues",
        "completed_history",
    ),
    InvestigationPromptName.DISCUSSION: (
        "session_id",
        "round_id",
        "case_introduction",
        "participant_id",
        "persona_profile",
        "visible_clues",
        "analyses",
        "completed_history",
        "discussion_history",
    ),
    InvestigationPromptName.DECISION: (
        "session_id",
        "round_id",
        "case_introduction",
        "visible_clues",
        "analyses",
        "hypotheses",
        "discussion_transcript",
    ),
    InvestigationPromptName.FINAL_THEORY: (
        "session_id",
        "case_introduction",
        "visible_clues",
        "hypotheses",
        "decisions",
    ),
}


class InvestigationPromptTemplate(BaseModel):
    """One immutable validated prompt template and its closed contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: InvestigationPromptName
    version: int
    body: str
    required_placeholders: tuple[str, ...]


def _coerce_prompt_name(value: InvestigationPromptName) -> InvestigationPromptName:
    try:
        return InvestigationPromptName(value)
    except (TypeError, ValueError) as error:
        raise InvestigationPromptError(f"unknown investigation prompt: {value!r}") from error


def load_investigation_prompt(
    prompt_name: InvestigationPromptName,
) -> InvestigationPromptTemplate:
    """Load one fixed UTF-8 prompt independently of the working directory."""
    resolved_name = _coerce_prompt_name(prompt_name)
    path = _PROMPT_DIRECTORY / _PROMPT_FILES[resolved_name]
    if not path.is_file():
        raise FileNotFoundError(f"investigation prompt file not found: {path}")

    text = path.read_text(encoding="utf-8")
    first_line, separator, remainder = text.partition("\n")
    version_match = _VERSION_PATTERN.fullmatch(first_line.rstrip("\r"))
    if version_match is None:
        raise InvestigationPromptError("malformed or missing Prompt-Version declaration")
    version = int(version_match.group(1))
    if version != SUPPORTED_PROMPT_VERSION:
        raise InvestigationPromptError(f"unsupported investigation prompt version: {version}")

    body = remainder.lstrip("\r\n") if separator else ""
    if not body.strip():
        raise InvestigationPromptError("investigation prompt body must not be empty")

    template = InvestigationPromptTemplate(
        name=resolved_name,
        version=version,
        body=body,
        required_placeholders=_REQUIRED_PLACEHOLDERS[resolved_name],
    )
    _validate_template_placeholders(template)
    return template


def _validate_template_placeholders(
    template: InvestigationPromptTemplate,
) -> tuple[str, ...]:
    found = tuple(_PLACEHOLDER_PATTERN.findall(template.body))
    body_without_placeholders = _PLACEHOLDER_PATTERN.sub("", template.body)
    if "{{" in body_without_placeholders or "}}" in body_without_placeholders:
        raise InvestigationPromptError(
            "prompt contains an unresolved or malformed placeholder"
        )
    found_set = set(found)
    required_set = set(template.required_placeholders)
    missing = required_set - found_set
    if missing:
        raise InvestigationPromptError(
            "prompt is missing required placeholders: " + ", ".join(sorted(missing))
        )
    unexpected = found_set - required_set
    if unexpected:
        raise InvestigationPromptError(
            "prompt contains unexpected placeholders: "
            + ", ".join(sorted(unexpected))
        )
    return found


def render_investigation_prompt(
    template: InvestigationPromptTemplate,
    values: Mapping[str, str],
) -> str:
    """Render a prompt once using its closed string-only placeholder contract."""
    if not isinstance(template, InvestigationPromptTemplate):
        raise InvestigationPromptError("template must be an InvestigationPromptTemplate")
    if not isinstance(values, Mapping):
        raise InvestigationPromptError("values must be a mapping")
    _validate_template_placeholders(template)

    required = set(template.required_placeholders)
    missing = required - set(values)
    if missing:
        raise InvestigationPromptError(
            "missing rendering values: " + ", ".join(sorted(missing))
        )
    unexpected = set(values) - required
    if unexpected:
        raise InvestigationPromptError(
            "unexpected rendering values: " + ", ".join(sorted(unexpected))
        )
    for name in template.required_placeholders:
        value = values[name]
        if not isinstance(value, str):
            raise InvestigationPromptError(f"rendering value {name!r} must be a string")
        if not value.strip():
            raise InvestigationPromptError(f"rendering value {name!r} must not be empty")

    return _PLACEHOLDER_PATTERN.sub(
        lambda match: values[match.group(1)],
        template.body,
    )


def render_visible_clues(
    session: InvestigationSession,
    visible_clue_ids: tuple[str, ...],
) -> str:
    """Render exactly the supplied ordered clue visibility snapshot."""
    if len(visible_clue_ids) != len(set(visible_clue_ids)):
        raise ValueError("visible_clue_ids must not contain duplicates")
    clue_by_id = {clue.clue_id: clue for clue in session.clues}
    lines = []
    for clue_id in visible_clue_ids:
        if clue_id not in clue_by_id:
            raise ValueError(f"unknown visible clue_id: {clue_id!r}")
        lines.append(f"[{clue_id}] {clue_by_id[clue_id].text}")
    return "\n".join(lines) if lines else "None."


def render_persona_context(persona: Persona) -> str:
    """Render one validated persona through the existing system-prompt path."""
    if not isinstance(persona, Persona):
        raise ValueError("persona must be a validated Persona")
    return build_system_prompt(persona, _PROMPT_DIRECTORY).strip()


def _render_evidence(items: Sequence[EvidenceReference]) -> str:
    if not items:
        return "none"
    return ", ".join(
        f"{item.clue_id}:{item.relation.value}" for item in items
    )


def _render_text_items(items: Sequence[str]) -> str:
    return " | ".join(items) if items else "none"


def render_analyses(analyses: Sequence[AgentAnalysis]) -> str:
    """Render analyses in supplied order without serializing model reprs."""
    if not analyses:
        return "None."
    return "\n".join(
        f"[{item.analysis_id}] {item.agent_id}; facts={_render_text_items(item.facts)}; "
        f"deductions={_render_text_items(item.deductions)}; "
        f"evidence={_render_evidence(item.evidence)}; "
        f"proposed_leads={_render_text_items(item.proposed_leads)}"
        for item in analyses
    )


def render_hypotheses(hypotheses: Sequence[Hypothesis]) -> str:
    """Render hypotheses in supplied order."""
    if not hypotheses:
        return "None."
    return "\n".join(
        f"[{item.hypothesis_id}] {item.status.value}: {item.statement}; "
        f"evidence={_render_evidence(item.evidence)}"
        for item in hypotheses
    )


def render_decisions(decisions: Sequence[GroupDecision]) -> str:
    """Render group decisions in supplied order."""
    if not decisions:
        return "None."
    return "\n".join(
        f"[{item.decision_id}] {item.decision_type.value}: {item.summary}; "
        f"evidence={_render_evidence(item.evidence)}"
        for item in decisions
    )


def render_discussion_messages(messages: Sequence[Message]) -> str:
    """Render discussion messages in their supplied chronological order."""
    if not messages:
        return "None."
    return "\n".join(
        f"[Turn {item.turn_index}] {item.speaker_name}: {item.text}"
        for item in messages
    )
