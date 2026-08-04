"""Deterministic filtering and construction of two-character blind trials."""

from collections import Counter
from dataclasses import dataclass
import hashlib
import random
import re
from collections.abc import Sequence

from multi_agent_personalities.models import ConversationRun, EvaluationTrial


PILOT_CHARACTER_IDS = ("sherlock_holmes", "hercule_poirot")
LEAK_PATTERN = re.compile(r"\b(?:sherlock(?:\s+holmes)?|holmes|hercule(?:\s+poirot)?|poirot)\b", re.IGNORECASE)


@dataclass(frozen=True)
class TrialBuildResult:
    trials: tuple[EvaluationTrial, ...]
    summary: dict[str, object]


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def build_trials(
    runs: Sequence[ConversationRun], *, trials_per_character: int = 3,
    seed: int = 42, minimum_text_length: int = 20,
    condition: str = "persona_seeded_mock",
) -> TrialBuildResult:
    """Build balanced deterministic trials, failing if either class is short."""
    if trials_per_character <= 0 or minimum_text_length <= 0:
        raise ValueError("trial count and minimum text length must be positive")
    eligible: dict[str, list[tuple[ConversationRun, object]]] = {key: [] for key in PILOT_CHARACTER_IDS}
    exclusions: Counter[str] = Counter()
    texts: Counter[str] = Counter()
    candidate_count = 0
    source_run_ids: list[str] = []
    for run in runs:
        if run.status != "completed":
            raise ValueError(f"source run is not completed: {run.run_id}")
        source_run_ids.append(run.run_id)
        for message in run.messages:
            candidate_count += 1
            reason = None
            if message.error is not None:
                reason = "malformed_message"
            elif message.speaker_character_id not in PILOT_CHARACTER_IDS:
                reason = "unsupported_speaker"
            elif not message.text.strip():
                reason = "empty_text"
            elif len(message.text.strip()) < minimum_text_length:
                reason = "below_minimum_length"
            elif LEAK_PATTERN.search(message.text):
                reason = "identity_leakage"
            if reason:
                exclusions[reason] += 1
                continue
            eligible[message.speaker_character_id].append((run, message))
            texts[message.text.strip()] += 1

    rng = random.Random(seed)
    selected: list[tuple[ConversationRun, object]] = []
    selected_per_run: dict[str, dict[str, int]] = {}
    if len(runs) != trials_per_character:
        raise ValueError(
            "one source run per configured topic is required for balanced trials"
        )
    for run in runs:
        selected_per_run[run.run_id] = {}
        for character_id in PILOT_CHARACTER_IDS:
            pool = sorted(
                (
                    item for item in eligible[character_id]
                    if item[0].run_id == run.run_id
                ),
                key=lambda item: item[1].message_id,
            )
            if not pool:
                raise ValueError(
                    "cannot build balanced trial sample; source run "
                    f"{run.run_id!r} has no eligible {character_id!r} message"
                )
            selected.append(rng.choice(pool))
            selected_per_run[run.run_id][character_id] = 1
    rng.shuffle(selected)

    trials = []
    accepted_per_character: Counter[str] = Counter()
    for run, message in selected:
        candidates = list(PILOT_CHARACTER_IDS)
        rng.shuffle(candidates)
        trial = EvaluationTrial(
            trial_id=_stable_id("trial", condition, run.run_id, message.message_id),
            source_run_id=run.run_id,
            source_message_id=message.message_id,
            condition=condition,
            display_text=message.text.strip(),
            candidate_character_ids=tuple(candidates),
            correct_character_id=message.speaker_character_id,
            source_provider=message.provider,
            synthetic_data=message.provider == "mock",
        )
        trials.append(trial)
        accepted_per_character[message.speaker_character_id] += 1

    duplicates = [
        {"text_sha256": hashlib.sha256(text.encode()).hexdigest(), "occurrences": count}
        for text, count in sorted(texts.items()) if count > 1
    ]
    summary = {
        "candidate_messages": candidate_count,
        "accepted_candidates": sum(len(items) for items in eligible.values()),
        "selected_trials": len(trials),
        "excluded_messages": sum(exclusions.values()),
        "exclusions_by_reason": dict(sorted(exclusions.items())),
        "accepted_trials_per_character": dict(accepted_per_character),
        "selected_trials_per_run_and_character": selected_per_run,
        "duplicate_text_warnings": duplicates,
        "source_run_ids": source_run_ids,
        "minimum_text_length": minimum_text_length,
    }
    return TrialBuildResult(tuple(trials), summary)
