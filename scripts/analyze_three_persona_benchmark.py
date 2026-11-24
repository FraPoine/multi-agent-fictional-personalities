#!/usr/bin/env python3
"""Recompute the benchmark's descriptive analysis from saved human ratings."""
import argparse
from pathlib import Path
from multi_agent_personalities.evaluation.benchmark_human import analyze_benchmark

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('benchmark_directory', type=Path)
args = parser.parse_args()
analyze_benchmark(args.benchmark_directory)
print(args.benchmark_directory / 'report.md')
