"""Explicit deterministic mock bindings for planned investigation phases."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType

from multi_agent_personalities.application.investigation_ids import (
    DeterministicInvestigationIdFactory,
)
from multi_agent_personalities.application.investigation_tasks import (
    investigation_analysis_task_name,
    investigation_discussion_task_name,
)
from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.llm.mock_provider import MockProvider
from multi_agent_personalities.models import GenerationResult


SHERLOCK_HOLMES_ID = "sherlock_holmes"
HERCULE_POIROT_ID = "hercule_poirot"


class InvestigationMockTask(str, Enum):
    """Stable task names for every deterministic two-round fixture."""

    SHERLOCK_ANALYSIS_ROUND_0001 = (
        "investigation.analysis.sherlock_holmes.round_0001"
    )
    POIROT_ANALYSIS_ROUND_0001 = (
        "investigation.analysis.hercule_poirot.round_0001"
    )
    SHERLOCK_DISCUSSION_ROUND_0001_TURN_0001 = (
        "investigation.discussion.sherlock_holmes.round_0001.turn_0001"
    )
    POIROT_DISCUSSION_ROUND_0001_TURN_0002 = (
        "investigation.discussion.hercule_poirot.round_0001.turn_0002"
    )
    DECISION_ROUND_0001 = "investigation.decision.round_0001"
    SHERLOCK_ANALYSIS_ROUND_0002 = (
        "investigation.analysis.sherlock_holmes.round_0002"
    )
    POIROT_ANALYSIS_ROUND_0002 = (
        "investigation.analysis.hercule_poirot.round_0002"
    )
    SHERLOCK_DISCUSSION_ROUND_0002_TURN_0001 = (
        "investigation.discussion.sherlock_holmes.round_0002.turn_0001"
    )
    POIROT_DISCUSSION_ROUND_0002_TURN_0002 = (
        "investigation.discussion.hercule_poirot.round_0002.turn_0002"
    )
    DECISION_ROUND_0002 = "investigation.decision.round_0002"
    FINAL_THEORY = "investigation.final_theory"


INVESTIGATION_FIXTURE_FILES: Mapping[InvestigationMockTask, str] = MappingProxyType(
    {
        InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0001: (
            "round_0001_sherlock_analysis.json"
        ),
        InvestigationMockTask.POIROT_ANALYSIS_ROUND_0001: (
            "round_0001_poirot_analysis.json"
        ),
        InvestigationMockTask.SHERLOCK_DISCUSSION_ROUND_0001_TURN_0001: (
            "round_0001_sherlock_discussion_turn_0001.txt"
        ),
        InvestigationMockTask.POIROT_DISCUSSION_ROUND_0001_TURN_0002: (
            "round_0001_poirot_discussion_turn_0002.txt"
        ),
        InvestigationMockTask.DECISION_ROUND_0001: "round_0001_decision.json",
        InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0002: (
            "round_0002_sherlock_analysis.json"
        ),
        InvestigationMockTask.POIROT_ANALYSIS_ROUND_0002: (
            "round_0002_poirot_analysis.json"
        ),
        InvestigationMockTask.SHERLOCK_DISCUSSION_ROUND_0002_TURN_0001: (
            "round_0002_sherlock_discussion_turn_0001.txt"
        ),
        InvestigationMockTask.POIROT_DISCUSSION_ROUND_0002_TURN_0002: (
            "round_0002_poirot_discussion_turn_0002.txt"
        ),
        InvestigationMockTask.DECISION_ROUND_0002: "round_0002_decision.json",
        InvestigationMockTask.FINAL_THEORY: "final_theory.json",
    }
)


_PARTICIPANT_TASKS: Mapping[str, tuple[InvestigationMockTask, ...]] = (
    MappingProxyType(
        {
            SHERLOCK_HOLMES_ID: (
                InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0001,
                InvestigationMockTask.SHERLOCK_DISCUSSION_ROUND_0001_TURN_0001,
                InvestigationMockTask.SHERLOCK_ANALYSIS_ROUND_0002,
                InvestigationMockTask.SHERLOCK_DISCUSSION_ROUND_0002_TURN_0001,
            ),
            HERCULE_POIROT_ID: (
                InvestigationMockTask.POIROT_ANALYSIS_ROUND_0001,
                InvestigationMockTask.POIROT_DISCUSSION_ROUND_0001_TURN_0002,
                InvestigationMockTask.POIROT_ANALYSIS_ROUND_0002,
                InvestigationMockTask.POIROT_DISCUSSION_ROUND_0002_TURN_0002,
            ),
        }
    )
)

_DEFAULT_FIXTURES_ROOT = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "investigation"
)
_SOURCE_SESSION_ID = DeterministicInvestigationIdFactory(1).session_id


@dataclass(frozen=True)
class _SessionScopedInvestigationMockProvider:
    """Scope canonical fixture references without specializing MockProvider."""

    provider: LLMProvider
    target_session_id: str

    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        generation = self.provider.generate(prompt, task_name=task_name)
        scoped_text = generation.text.replace(
            _SOURCE_SESSION_ID,
            self.target_session_id,
        )
        if scoped_text == generation.text:
            return generation
        return GenerationResult(text=scoped_text, metadata=generation.metadata)


@dataclass(frozen=True)
class InvestigationMockBindings:
    """Immutable explicit participant and group-level provider bindings."""

    participant_providers: Mapping[str, LLMProvider]
    decision_provider: LLMProvider
    final_theory_provider: LLMProvider


def _paths_for_tasks(
    fixtures_root: Path,
    tasks: tuple[InvestigationMockTask, ...],
) -> Mapping[str, Path]:
    return MappingProxyType(
        {
            task.value: fixtures_root / INVESTIGATION_FIXTURE_FILES[task]
            for task in tasks
        }
    )


def _scope_provider(
    provider: LLMProvider,
    *,
    target_session_id: str,
) -> LLMProvider:
    if target_session_id == _SOURCE_SESSION_ID:
        return provider
    return _SessionScopedInvestigationMockProvider(
        provider=provider,
        target_session_id=target_session_id,
    )


def build_investigation_mock_bindings(
    fixtures_root: Path | None = None,
    *,
    session_sequence: int = 1,
) -> InvestigationMockBindings:
    """Build fixed fixture providers scoped to one deterministic session."""
    target_session_id = DeterministicInvestigationIdFactory(
        session_sequence
    ).session_id
    root = _DEFAULT_FIXTURES_ROOT if fixtures_root is None else Path(fixtures_root)
    participant_providers = MappingProxyType(
        {
            participant_id: _scope_provider(
                MockProvider(_paths_for_tasks(root, tasks)),
                target_session_id=target_session_id,
            )
            for participant_id, tasks in _PARTICIPANT_TASKS.items()
        }
    )
    return InvestigationMockBindings(
        participant_providers=participant_providers,
        decision_provider=_scope_provider(
            MockProvider(
                _paths_for_tasks(
                    root,
                    (
                        InvestigationMockTask.DECISION_ROUND_0001,
                        InvestigationMockTask.DECISION_ROUND_0002,
                    ),
                ),
            ),
            target_session_id=target_session_id,
        ),
        final_theory_provider=_scope_provider(
            MockProvider(
                _paths_for_tasks(root, (InvestigationMockTask.FINAL_THEORY,))
            ),
            target_session_id=target_session_id,
        ),
    )
