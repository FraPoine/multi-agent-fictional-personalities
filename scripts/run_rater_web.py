#!/usr/bin/env python3
"""Start the separate local blind-rater interface."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import uvicorn
from multi_agent_personalities.web.rater_app import create_rater_app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-id", required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    directory = args.output_root / "evaluation" / "pilots" / args.pilot_id
    app = create_rater_app(pilot_directory=directory, pilot_id=args.pilot_id)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
