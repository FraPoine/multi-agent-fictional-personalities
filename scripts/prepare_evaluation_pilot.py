#!/usr/bin/env python3
"""Prepare the deterministic two-character technical pilot."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from multi_agent_personalities.application.evaluation_service import prepare_technical_pilot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-id")
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "evaluation_pilot.yaml")
    args = parser.parse_args()
    result = prepare_technical_pilot(output_root=args.output_root, project_root=ROOT, config_path=args.config, pilot_id=args.pilot_id)
    print(f"Pilot ID: {result.pilot_id}")
    print(f"Directory: {result.pilot_directory}")
    print(f"Next: python scripts/run_rater_web.py --pilot-id {result.pilot_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
