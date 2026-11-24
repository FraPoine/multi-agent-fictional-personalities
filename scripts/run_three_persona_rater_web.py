#!/usr/bin/env python3
"""Serve an approved benchmark locally."""
import argparse
from pathlib import Path
import uvicorn
from multi_agent_personalities.web.rater_app import create_three_persona_rater_app

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('benchmark_directory', type=Path)
parser.add_argument('--host', default='127.0.0.1')
parser.add_argument('--port', type=int, default=8001)
args = parser.parse_args()
uvicorn.run(create_three_persona_rater_app(benchmark_directory=args.benchmark_directory), host=args.host, port=args.port)
