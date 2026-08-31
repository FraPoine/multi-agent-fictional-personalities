"""Catalogue-driven assembly for one deterministic mock investigation runtime."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from multi_agent_personalities.application.investigation_ids import (
    DeterministicInvestigationIdFactory,
)
from multi_agent_personalities.application.investigation_mock import (
    build_investigation_mock_bindings,
)
from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.models import Persona
from multi_agent_personalities.pipeline import CharacterConfig, character_registry
from multi_agent_personalities.simulation import ConversationParticipant


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SUPPORTED_ROUNDS = 2
_DISCUSSION_TURNS = 2


@dataclass(frozen=True)
class InvestigationMockCapabilities:
    """Fixture coverage metadata, never aggregate/domain limits."""

    participant_ids: tuple[str, ...]
    supported_rounds: int
    discussion_turns: int
    available_lead_fixture_refs: tuple[str, ...] = (
        "lead_a",
        "lead_b",
        "lead_a_revisit",
    )
    # Total supported (visit_index, segment_index) fixture combinations.
    available_discussion_segments: int = 4


@dataclass(frozen=True)
class InvestigationMockRuntime:
    """Dependencies required to execute one deterministic investigation."""

    id_factory: DeterministicInvestigationIdFactory
    character_configs: tuple[CharacterConfig, ...]
    participants: tuple[ConversationParticipant, ...]
    decision_provider: LLMProvider
    final_theory_provider: LLMProvider
    capabilities: InvestigationMockCapabilities

    @property
    def participant_ids(self) -> tuple[str, ...]:
        """Return executable participant identities in scenario order."""
        return tuple(item.character_id for item in self.participants)

    @property
    def character_slugs(self) -> tuple[str, ...]:
        """Return catalogue slugs in the same executable order."""
        return tuple(item.slug for item in self.character_configs)


def _capabilities_for_participants(
    participant_ids: tuple[str, ...],
) -> InvestigationMockCapabilities:
    return InvestigationMockCapabilities(
        participant_ids=participant_ids,
        supported_rounds=_SUPPORTED_ROUNDS,
        discussion_turns=_DISCUSSION_TURNS,
    )


def investigation_mock_capabilities() -> InvestigationMockCapabilities:
    """Describe the fixed scenario without executing provider generation."""
    bindings = build_investigation_mock_bindings()
    return _capabilities_for_participants(
        tuple(bindings.participant_providers)
    )


def _validate_character_slugs(character_slugs: Sequence[str]) -> tuple[str, ...]:
    if isinstance(character_slugs, (str, bytes)) or not isinstance(
        character_slugs, Sequence
    ):
        raise ValueError("character_slugs must be a sequence of strings")
    if any(not isinstance(slug, str) for slug in character_slugs):
        raise ValueError("character_slugs must contain only strings")
    selected = tuple(character_slugs)
    if len(selected) < 2:
        raise ValueError("at least two characters are required")
    if len(selected) != len(set(selected)):
        raise ValueError("characters must not contain duplicates")
    return selected


def _load_persona(config: CharacterConfig) -> Persona:
    try:
        persona = Persona.model_validate_json(
            config.persona_fixture.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as error:
        raise ValueError(
            f"invalid investigation persona fixture for {config.slug!r}: {error}"
        ) from error
    if (persona.character_id, persona.display_name) != (
        config.character_id,
        config.display_name,
    ):
        raise ValueError(
            f"investigation persona identity does not match {config.slug!r}"
        )
    return persona


def build_investigation_mock_runtime(
    *,
    character_slugs: Sequence[str],
    session_sequence: int,
    project_root: Path | None = None,
) -> InvestigationMockRuntime:
    """Assemble one catalogue-backed runtime for the fixed mock scenario."""
    selected_slugs = _validate_character_slugs(character_slugs)
    id_factory = DeterministicInvestigationIdFactory(session_sequence)
    bindings = build_investigation_mock_bindings(
        session_sequence=session_sequence
    )
    capabilities = _capabilities_for_participants(
        tuple(bindings.participant_providers)
    )

    resolved_project_root = (
        _PROJECT_ROOT if project_root is None else Path(project_root)
    )
    registry = character_registry(resolved_project_root)
    unknown_slugs = tuple(slug for slug in selected_slugs if slug not in registry)
    if unknown_slugs:
        known = ", ".join(registry)
        raise ValueError(
            f"unknown catalogue character: {unknown_slugs[0]!r}. Known: {known}"
        )

    selected_configs = tuple(registry[slug] for slug in selected_slugs)
    supported_ids = set(capabilities.participant_ids)
    unsupported = tuple(
        config
        for config in selected_configs
        if config.character_id not in supported_ids
    )
    if unsupported:
        raise ValueError(
            "catalogue character is unsupported by the current investigation "
            f"mock scenario: {unsupported[0].slug!r}"
        )

    config_by_id = {config.character_id: config for config in selected_configs}
    if set(config_by_id) != supported_ids:
        required = ", ".join(capabilities.participant_ids)
        raise ValueError(
            "current investigation mock scenario requires exactly these "
            f"participant IDs: {required}"
        )
    ordered_configs = tuple(
        config_by_id[participant_id]
        for participant_id in capabilities.participant_ids
    )

    participants: list[ConversationParticipant] = []
    for config in ordered_configs:
        provider = bindings.participant_providers.get(config.character_id)
        if provider is None:
            raise ValueError(
                "no investigation mock provider for catalogue character "
                f"{config.slug!r}"
            )
        participants.append(
            ConversationParticipant(
                persona=_load_persona(config),
                provider=provider,
                provider_name="mock",
            )
        )

    return InvestigationMockRuntime(
        id_factory=id_factory,
        character_configs=ordered_configs,
        participants=tuple(participants),
        decision_provider=bindings.decision_provider,
        final_theory_provider=bindings.final_theory_provider,
        capabilities=capabilities,
    )
