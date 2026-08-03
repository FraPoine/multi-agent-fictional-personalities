"""CLI for deterministic synthetic multi-agent conversations."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from multi_agent_personalities.artifacts import save_conversation_run
from multi_agent_personalities.llm import RoundRobinMockProvider
from multi_agent_personalities.models import Persona, validate_run_id
from multi_agent_personalities.pipeline import character_registry
from multi_agent_personalities.simulation import simulate_chat


PROJECT_ROOT = Path(__file__).resolve().parents[3]


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


def _load_inputs(character_slugs: Sequence[str]) -> tuple[list[Persona], list[str]]:
    if len(character_slugs) < 2:
        raise ValueError("at least two characters are required")
    if len(character_slugs) != len(set(character_slugs)):
        raise ValueError("characters must not contain duplicates")

    registry = character_registry(PROJECT_ROOT)
    unsupported = [slug for slug in character_slugs if slug not in registry]
    if unsupported:
        supported = ", ".join(registry)
        raise ValueError(
            f"unsupported character: {unsupported[0]!r}. Supported: {supported}"
        )

    personas: list[Persona] = []
    responses: list[str] = []
    for slug in character_slugs:
        config = registry[slug]
        try:
            persona = Persona.model_validate_json(
                config.persona_fixture.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as error:
            raise ValueError(
                f"invalid synthetic persona fixture for {slug!r}: {error}"
            ) from error
        if (persona.character_id, persona.display_name) != (
            config.character_id,
            config.display_name,
        ):
            raise ValueError(
                f"synthetic persona identity does not match {slug!r}"
            )
        try:
            response = config.agent_response_fixture.read_text(encoding="utf-8")
        except OSError as error:
            raise ValueError(
                f"invalid synthetic response fixture for {slug!r}: {error}"
            ) from error
        if not response.strip():
            raise ValueError(f"synthetic response fixture for {slug!r} is empty")
        personas.append(persona)
        responses.append(response)
    return personas, responses


def main(argv: Sequence[str] | None = None) -> int:
    """Run one synthetic conversation, returning a process-style exit code."""
    try:
        args = _parser().parse_args(argv)
        if args.provider != "mock":
            raise ValueError(
                f"unsupported provider: {args.provider!r}. Supported: mock"
            )
        if args.run_id is not None:
            validate_run_id(args.run_id)
        personas, responses = _load_inputs(args.characters)
        provider = RoundRobinMockProvider(responses)
        run = simulate_chat(
            personas=personas,
            topic=args.topic,
            turn_count=args.turn_count,
            provider=provider,
            provider_name="mock",
            model_name="mock-round-robin",
            seed=args.seed,
            run_id=args.run_id,
        )
        directory = save_conversation_run(output_root=args.output_root, run=run)
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
    print(f"Run ID: {run.run_id}")
    print(f"Turns: {len(run.messages)}")
    print(f"Artifacts: {directory}")
    print(f"Transcript: {directory / 'transcript.md'}")
    return 0
