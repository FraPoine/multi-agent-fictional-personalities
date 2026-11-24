#!/usr/bin/env python3
"""Import six previously generated runs; never invokes a model."""
import argparse
from pathlib import Path

from multi_agent_personalities.evaluation.benchmark import prepare_three_persona_benchmark


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_manifest", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    parser.add_argument("--config", type=Path, default=Path("configs/benchmark_three_personas_v1.yaml"))
    args = parser.parse_args()
    print(prepare_three_persona_benchmark(source_manifest=args.source_manifest, output_root=args.output_root, config_path=args.config))


if __name__ == "__main__":
    main()
