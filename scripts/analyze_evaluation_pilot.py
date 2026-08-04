#!/usr/bin/env python3
"""Recompute analysis and report from persisted pilot inputs."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from multi_agent_personalities.evaluation.persistence import refresh_analysis

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--pilot-id", required=True)
parser.add_argument("--output-root", type=Path, default=ROOT / "outputs")
parser.add_argument(
    "--response-source",
    choices=("human", "synthetic"),
    default="human",
    help="Analyze genuine responses by default; synthetic data is explicit.",
)
args = parser.parse_args()
analysis = refresh_analysis(
    args.output_root / "evaluation" / "pilots" / args.pilot_id,
    response_source=args.response_source,
)
print(f"Response source: {analysis['response_source']}")
print(f"Responses: {analysis['total_response_count']}")
print(f"Accuracy: {analysis['overall_accuracy']}")
