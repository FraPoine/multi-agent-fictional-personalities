#!/usr/bin/env python3
"""Development-only deterministic synthetic response fixture generator."""

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from multi_agent_personalities.evaluation.persistence import (
    load_jsonl,
    save_synthetic_responses,
)
from multi_agent_personalities.models import PublicEvaluationTrial, RaterResponse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--pilot-id", required=True)
parser.add_argument("--output-root", type=Path, default=ROOT / "outputs")
parser.add_argument("--confirm-development-only", action="store_true", required=True)
args = parser.parse_args()
directory = args.output_root / "evaluation" / "pilots" / args.pilot_id
trials = load_jsonl(directory / "trials_public.jsonl", PublicEvaluationTrial)
responses = []
fixture_timestamp = datetime(2026, 8, 4, tzinfo=timezone.utc)
for rater_index in range(1, 3):
    for index, trial in enumerate(trials):
        selected = trial.candidate_character_ids[(index + rater_index) % 2]
        response_id = "synthetic_" + hashlib.sha256(f"{args.pilot_id}:{rater_index}:{trial.trial_id}".encode()).hexdigest()[:20]
        responses.append(RaterResponse(response_id=response_id, trial_id=trial.trial_id, rater_id=f"synthetic_rater_{rater_index}", selected_character_id=selected, confidence=3, timestamp=fixture_timestamp, synthetic_data=True))
save_synthetic_responses(directory, responses)
print("Created development-only synthetic responses (synthetic_data=true).")
