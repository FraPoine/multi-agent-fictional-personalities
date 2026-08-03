"""CLI for deterministic synthetic multi-agent conversations."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from multi_agent_personalities.application import run_mock_conversation
from multi_agent_personalities.artifacts import save_conversation_run


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        description="Run a deterministic synthetic mock conversation."
    )
    parser.add_argument("--characters", nargs="+", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--turn-count", type=_positive_integer, default=6)
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    parser.add_argument("--run-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one synthetic conversation, returning a process-style exit code."""
    try:
        args = _parser().parse_args(argv)
        if args.provider != "mock":
            raise ValueError(
                f"unsupported provider: {args.provider!r}. Supported: mock"
            )
        result = run_mock_conversation(
            character_slugs=args.characters,
            topic=args.topic,
            turn_count=args.turn_count,
            seed=args.seed,
            output_root=args.output_root,
            run_id=args.run_id,
            _save_run=save_conversation_run,
        )
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(
            f"Error: unable to save conversation artifacts: {error}",
            file=sys.stderr,
        )
        return 2

    print("Conversation completed.")
    print(f"Run ID: {result.run_id}")
    print(f"Turns: {len(result.run.messages)}")
    print(f"Artifacts: {result.artifact_directory}")
    print(f"Transcript: {result.transcript_path}")
    return 0
