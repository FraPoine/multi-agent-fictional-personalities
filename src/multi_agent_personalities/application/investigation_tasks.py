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
