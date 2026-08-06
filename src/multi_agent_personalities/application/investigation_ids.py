"""Deterministic identifiers for stateless investigation operations."""

from dataclasses import dataclass

from multi_agent_personalities.models import validate_run_id


def _require_strict_integer(value: object, *, name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer greater than or equal to {minimum}")
    return value


@dataclass(frozen=True)
class DeterministicInvestigationIdFactory:
    """Build one validated, reproducible investigation ID namespace."""

    session_sequence: int

    def __post_init__(self) -> None:
        _require_strict_integer(
            self.session_sequence,
            name="session_sequence",
            minimum=1,
        )

    @property
    def session_id(self) -> str:
        """Return the one-based session identifier for this namespace."""
        return validate_run_id(f"session_{self.session_sequence:03d}")

    def clue_id(self, reveal_order: int) -> str:
        """Return a one-based clue identifier for a zero-based reveal order."""
        reveal_order = _require_strict_integer(
            reveal_order,
            name="reveal_order",
            minimum=0,
        )
        return validate_run_id(
            f"{self.session_id}_clue_{reveal_order + 1:04d}"
        )

    def round_id(self, round_index: int) -> str:
        """Return an identifier for a one-based round index."""
        round_index = _require_strict_integer(
            round_index,
            name="round_index",
            minimum=1,
        )
        return validate_run_id(
            f"{self.session_id}_round_{round_index:04d}"
        )

    def analysis_id(self, participant_id: str, round_index: int) -> str:
        """Return the canonical participant analysis ID for one round."""
        participant_id = validate_run_id(participant_id)
        round_index = _require_strict_integer(
            round_index,
            name="round_index",
            minimum=1,
        )
        return validate_run_id(
            f"{self.session_id}_analysis_{participant_id}_{round_index:04d}"
        )

    def hypothesis_id(self, hypothesis_index: int) -> str:
        """Return the canonical one-based session hypothesis ID."""
        hypothesis_index = _require_strict_integer(
            hypothesis_index,
            name="hypothesis_index",
            minimum=1,
        )
        return validate_run_id(
            f"{self.session_id}_hypothesis_{hypothesis_index:04d}"
        )

    def discussion_run_id(self, round_index: int) -> str:
        """Return the canonical conversation run ID for one round discussion."""
        round_index = _require_strict_integer(
            round_index,
            name="round_index",
            minimum=1,
        )
        return validate_run_id(
            f"{self.round_id(round_index)}_discussion"
        )
