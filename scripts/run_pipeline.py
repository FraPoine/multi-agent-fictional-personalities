"""Run the current Poirot pipeline with deterministic mock LLM outputs."""

import argparse
from pathlib import Path

from multi_agent_personalities.pipeline import (
    default_pipeline_paths,
    run_pipeline,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the synthetic Poirot development pipeline."
    )
    parser.add_argument("--character", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--message", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_directory = run_pipeline(
        character=args.character,
        provider_name=args.provider,
        user_message=args.message,
        output_root=PROJECT_ROOT / "outputs",
        paths=default_pipeline_paths(PROJECT_ROOT),
    )
    print("Synthetic mock pipeline completed successfully.")
    print(f"Output directory: {run_directory}")


if __name__ == "__main__":
    main()
