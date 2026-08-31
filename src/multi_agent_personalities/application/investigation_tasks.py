"""Provider-neutral deterministic task names for investigation operations."""

from multi_agent_personalities.models import validate_run_id


def investigation_analysis_task_name(participant_id: str, round_index: int) -> str:
    """Return the stable analysis task name for explicit participant/round input."""
    participant_id = validate_run_id(participant_id)
    if (
        isinstance(round_index, bool)
        or not isinstance(round_index, int)
        or round_index < 1
    ):
        raise ValueError("round_index must be a positive integer")
    return f"investigation.analysis.{participant_id}.round_{round_index:04d}"


def investigation_discussion_task_name(
    participant_id: str,
    round_index: int,
    turn_index: int,
) -> str:
    """Return a stable task name from explicit participant, round, and turn."""
    participant_id = validate_run_id(participant_id)
    for value, name in ((round_index, "round_index"), (turn_index, "turn_index")):
        minimum = 1 if name == "round_index" else 0
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < minimum
        ):
            raise ValueError(f"{name} must be an integer >= {minimum}")
    return (
        f"investigation.discussion.{participant_id}."
        f"round_{round_index:04d}.turn_{turn_index + 1:04d}"
    )


def investigation_decision_task_name(round_index: int) -> str:
    """Return the stable group-decision task name for a one-based round."""
    if (
        isinstance(round_index, bool)
        or not isinstance(round_index, int)
        or round_index < 1
    ):
        raise ValueError("round_index must be a positive integer")
    return f"investigation.decision.round_{round_index:04d}"


def investigation_final_theory_task_name() -> str:
    """Return the stable provider-neutral final-theory task name."""
    return "investigation.final_theory"


def investigation_lead_final_theory_task_name() -> str:
    """Return the stable task name for Lead/Visit finalization."""
    return "investigation.lead_visit.final_theory"


def investigation_lead_discussion_task_name(
    participant_id: str,
    visit_index: int,
    segment_index: int,
    turn_index: int,
) -> str:
    """Return a semantic task name for one Lead/Visit discussion turn."""
    participant_id = validate_run_id(participant_id)
    for value, name, minimum in (
        (visit_index, "visit_index", 1),
        (segment_index, "segment_index", 1),
        (turn_index, "turn_index", 0),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    return (
        f"investigation.lead_visit.discussion.{participant_id}."
        f"visit_{visit_index:04d}.segment_{segment_index:04d}."
        f"turn_{turn_index + 1:04d}"
    )
