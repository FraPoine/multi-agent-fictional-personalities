#!/usr/bin/env python3
"""Record approval after inspecting every trial and the private leakage report."""
import argparse
from pathlib import Path
from multi_agent_personalities.evaluation.benchmark_human import approve_review

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('benchmark_directory', type=Path)
parser.add_argument('--reviewer', required=True, help='pseudonymous reviewer identifier')
parser.add_argument('--confirm-reviewed', action='store_true', required=True, help='confirm all 18 trials and the leakage report were inspected')
args = parser.parse_args()
print(approve_review(args.benchmark_directory, args.reviewer))
