"""Explicit deterministic mock bindings for planned investigation phases."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType

from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.llm.mock_provider import MockProvider
from multi_agent_personalities.models import validate_run_id


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


@dataclass(frozen=True)
class InvestigationMockBindings:
    """Immutable explicit participant and group-level provider bindings."""

    participant_providers: Mapping[str, LLMProvider]
    decision_provider: LLMProvider
    final_theory_provider: LLMProvider


def investigation_analysis_task_name(
    participant_id: str,
    round_index: int,
) -> str:
    """Return the stable analysis task name for explicit participant/round input."""
    participant_id = validate_run_id(participant_id)
    if (
        isinstance(round_index, bool)
        or not isinstance(round_index, int)
        or round_index < 1
    ):
        raise ValueError("round_index must be a positive integer")
    return f"investigation.analysis.{participant_id}.round_{round_index:04d}"


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


def build_investigation_mock_bindings(
    fixtures_root: Path | None = None,
) -> InvestigationMockBindings:
    """Build call-order-independent providers over the fixed fixture inventory."""
    root = _DEFAULT_FIXTURES_ROOT if fixtures_root is None else Path(fixtures_root)
    participant_providers = MappingProxyType(
        {
            participant_id: MockProvider(_paths_for_tasks(root, tasks))
            for participant_id, tasks in _PARTICIPANT_TASKS.items()
        }
    )
    return InvestigationMockBindings(
        participant_providers=participant_providers,
        decision_provider=MockProvider(
            _paths_for_tasks(
                root,
                (
                    InvestigationMockTask.DECISION_ROUND_0001,
                    InvestigationMockTask.DECISION_ROUND_0002,
                ),
            )
        ),
        final_theory_provider=MockProvider(
            _paths_for_tasks(root, (InvestigationMockTask.FINAL_THEORY,))
        ),
    )
