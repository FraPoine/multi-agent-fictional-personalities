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
args = parser.parse_args()
analysis = refresh_analysis(args.output_root / "evaluation" / "pilots" / args.pilot_id)
print(f"Responses: {analysis['total_response_count']}")
print(f"Accuracy: {analysis['overall_accuracy']}")
