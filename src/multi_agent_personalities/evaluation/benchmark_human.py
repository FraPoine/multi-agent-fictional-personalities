"""Reviewed human-rating storage and descriptive analysis for the benchmark."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import random
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from multi_agent_personalities.evaluation.analysis import _wilson_interval
from multi_agent_personalities.evaluation.benchmark import IDS, PublicBenchmarkTrial
from multi_agent_personalities.evaluation.persistence import _pilot_lock, _replace_text, load_jsonl

CHARACTERS = tuple(IDS.values())
REVIEW_FILES = ('trials_public.jsonl', 'answer_key.jsonl', 'benchmark_manifest.json', 'leakage_review.json')
RATER_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$')


class Familiarity(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    benchmark_id: str
    rater_id: str
    scores: dict[str, int]
    timestamp: datetime

    @field_validator('scores')
    @classmethod
    def validate_scores(cls, value):
        if set(value) != set(CHARACTERS) or any(type(v) is not int or not 0 <= v <= 3 for v in value.values()):
            raise ValueError('familiarity requires scores 0 to 3 for all characters')
        return value


class BenchmarkResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    benchmark_id: str
    trial_id: str
    rater_id: str
    selected_character_id: str
    confidence: int = Field(strict=True, ge=1, le=5)
    timestamp: datetime


def _records(directory, name, model):
    path = directory / name
    return load_jsonl(path, model) if path.exists() else []


def _hashes(directory):
    return {name: sha256((directory / name).read_bytes()).hexdigest() for name in REVIEW_FILES}


def load_public(directory):
    trials = load_jsonl(directory / 'trials_public.jsonl', PublicBenchmarkTrial)
    if len(trials) != 18 or len({t.trial_id for t in trials}) != 18 or any(set(t.candidate_character_ids) != set(CHARACTERS) for t in trials):
        raise ValueError('invalid benchmark public trials')
    return trials


def approve_review(directory, reviewer):
    directory = Path(directory)
    if not RATER_ID.fullmatch(reviewer):
        raise ValueError('reviewer identifier must be 3–64 letters, digits, underscores or hyphens')
    with _pilot_lock(directory):
        load_public(directory)
        if (directory / 'review_approval.json').exists():
            raise ValueError('review already approved; rebuild to create a new reviewed set')
        if _records(directory, 'familiarity.jsonl', Familiarity) or _records(directory, 'responses.jsonl', BenchmarkResponse):
            raise ValueError('cannot approve after data collection began')
        approval = {'status': 'approved', 'reviewer_id': reviewer, 'timestamp': datetime.now(timezone.utc).isoformat(), 'sha256': _hashes(directory)}
        _replace_text(directory / 'review_approval.json', json.dumps(approval, indent=2) + '\n')
    return approval


def require_review(directory):
    try:
        approval = json.loads((directory / 'review_approval.json').read_text())
        if approval['status'] != 'approved' or approval['sha256'] != _hashes(directory):
            raise ValueError('review approval does not match current artifacts')
    except (OSError, KeyError, json.JSONDecodeError) as error:
        raise ValueError('benchmark has no valid manual review approval') from error
    return approval


def _manifest(directory):
    manifest = json.loads((directory / 'benchmark_manifest.json').read_text())
    if manifest['benchmark_id'] != 'three_personas_v1' or manifest['trial_count'] != 18 or type(manifest.get('seed')) is not int:
        raise ValueError('invalid benchmark manifest')
    return manifest


def _append(directory, name, records):
    _replace_text(directory / name, ''.join(record.model_dump_json() + '\n' for record in records))


def submit_familiarity(directory, rater_id, scores):
    directory = Path(directory)
    if not RATER_ID.fullmatch(rater_id):
        raise ValueError('invalid pseudonymous rater ID')
    with _pilot_lock(directory):
        require_review(directory)
        manifest = _manifest(directory)
        records = _records(directory, 'familiarity.jsonl', Familiarity)
        if any(record.rater_id == rater_id for record in records):
            raise ValueError('familiarity already submitted')
        if any(record.rater_id == rater_id for record in _records(directory, 'responses.jsonl', BenchmarkResponse)):
            raise ValueError('cannot add familiarity after evaluation begins')
        record = Familiarity(benchmark_id=manifest['benchmark_id'], rater_id=rater_id, scores=scores, timestamp=datetime.now(timezone.utc))
        _append(directory, 'familiarity.jsonl', [*records, record])
    return record


def submit_response(directory, rater_id, trial_id, selected, confidence):
    directory = Path(directory)
    if not RATER_ID.fullmatch(rater_id):
        raise ValueError('invalid pseudonymous rater ID')
    with _pilot_lock(directory):
        require_review(directory)
        manifest = _manifest(directory)
        trials = {item.trial_id: item for item in load_public(directory)}
        if trial_id not in trials or selected not in trials[trial_id].candidate_character_ids:
            raise ValueError('invalid trial or character selection')
        if not any(item.rater_id == rater_id for item in _records(directory, 'familiarity.jsonl', Familiarity)):
            raise ValueError('complete familiarity screening first')
        records = _records(directory, 'responses.jsonl', BenchmarkResponse)
        if any(x.rater_id == rater_id and x.trial_id == trial_id for x in records):
            raise ValueError('response already submitted')
        record = BenchmarkResponse(benchmark_id=manifest['benchmark_id'], trial_id=trial_id, rater_id=rater_id, selected_character_id=selected, confidence=confidence, timestamp=datetime.now(timezone.utc))
        _append(directory, 'responses.jsonl', [*records, record])
    return record


def rater_order(trials, seed, rater_id):
    digest = sha256(f'{seed}\x1f{rater_id}'.encode()).digest()
    rng = random.Random(int.from_bytes(digest, 'big'))
    ordered = sorted(trials, key=lambda x: x.trial_id)
    rng.shuffle(ordered)
    choices = {}
    for trial in ordered:
        values = list(CHARACTERS)
        rng.shuffle(values)
        choices[trial.trial_id] = values
    return ordered, choices


def analyze_benchmark(directory):
    directory = Path(directory)
    with _pilot_lock(directory):
        approval = require_review(directory)
        manifest = _manifest(directory)
        trials = load_public(directory)
        answers = [json.loads(line) for line in (directory / 'answer_key.jsonl').read_text().splitlines() if line.strip()]
        answer = {a['trial_id']: a for a in answers}
        if len(answer) != 18 or set(answer) != {t.trial_id for t in trials} or any(a['correct_character_id'] not in CHARACTERS for a in answers):
            raise ValueError('answer key does not match trials')
        familiarity = _records(directory, 'familiarity.jsonl', Familiarity)
        responses = _records(directory, 'responses.jsonl', BenchmarkResponse)
        raters = {f.rater_id: f for f in familiarity}
        if len(raters) != len(familiarity) or any(f.benchmark_id != manifest['benchmark_id'] for f in familiarity):
            raise ValueError('invalid familiarity records')
        seen = set()
        for r in responses:
            key = (r.rater_id, r.trial_id)
            if key in seen or r.rater_id not in raters or r.trial_id not in answer or r.benchmark_id != manifest['benchmark_id'] or r.selected_character_id not in CHARACTERS:
                raise ValueError('invalid or duplicate response')
            seen.add(key)
        by_rater = {r: [x for x in responses if x.rater_id == r] for r in raters}
        completed = {r for r, items in by_rater.items() if len(items) == len(trials)}
        eligible = {r for r in completed if min(raters[r].scores.values()) >= 2}
        correct = lambda r: r.selected_character_id == answer[r.trial_id]['correct_character_id']
        def metric(items):
            n = len(items)
            k = sum(correct(x) for x in items)
            lo, hi = _wilson_interval(k, n)
            return {'responses': n, 'correct': k, 'incorrect': n - k, 'accuracy': k / n if n else None, 'naive_wilson_95': [lo, hi]}
        matrix = {c: {d: 0 for d in CHARACTERS} for c in CHARACTERS}
        for r in responses:
            matrix[answer[r.trial_id]['correct_character_id']][r.selected_character_id] += 1
        per_character = {c: metric([r for r in responses if answer[r.trial_id]['correct_character_id'] == c]) for c in CHARACTERS}
        confidence = lambda items: sum(r.confidence for r in items) / len(items) if items else None
        agreement_pairs = [(a, b) for a, b in combinations(responses, 2) if a.trial_id == b.trial_id and a.rater_id != b.rater_id]
        report = {'benchmark_id': manifest['benchmark_id'], 'trial_count': len(trials), 'source_run_count': len(manifest['sources']), 'model': manifest['model'], 'review': approval, 'chance_baseline': 1 / 3, 'rater_count': len(raters), 'completed_raters': len(completed), 'incomplete_raters': len(raters) - len(completed), 'eligible_complete_raters': len(eligible), 'primary_familiar_complete': metric([r for r in responses if r.rater_id in eligible]), 'all_responses': metric(responses), 'per_character': per_character, 'confusion_matrix': matrix, 'per_rater': {r: metric(items) for r, items in by_rater.items()}, 'mean_confidence_correct': confidence([r for r in responses if correct(r)]), 'mean_confidence_incorrect': confidence([r for r in responses if not correct(r)]), 'familiarity_distribution': {c: {str(score): sum(f.scores[c] == score for f in familiarity) for score in range(4)} for c in CHARACTERS}, 'responses_per_scenario': {s: sum(answer[r.trial_id]['scenario_id'] == s for r in responses) for s in sorted(manifest['sources'])}, 'agreement': {'matching_pairs': sum(a.selected_character_id == b.selected_character_id for a, b in agreement_pairs), 'overlapping_pairs': len(agreement_pairs), 'pairwise_percentage': sum(a.selected_character_id == b.selected_character_id for a, b in agreement_pairs) / len(agreement_pairs) if agreement_pairs else None}, 'limitations': 'Naive Wilson 95% intervals treat judgments as independent; repeated raters and shared source conversations violate independence. This exploratory development benchmark does not establish statistical significance, behavioral fidelity, or authentic personality reproduction.'}
        _replace_text(directory / 'analysis.json', json.dumps(report, indent=2) + '\n')
        _replace_text(directory / 'report.md', render_report(report))
    return report


def render_report(data):
    def pct(metric):
        value = metric['accuracy']
        return 'unavailable' if value is None else f'{value:.1%} ({metric["correct"]}/{metric["responses"]})'
    return ('# Three-persona development benchmark\n\n'
        f"- Benchmark: {data['benchmark_id']}; model: {data['model']}\n"
        f"- Sources: {data['source_run_count']}; unique trials: {data['trial_count']}\n"
        f"- Raters: {data['rater_count']}; complete: {data['completed_raters']}; incomplete: {data['incomplete_raters']}; eligible complete: {data['eligible_complete_raters']}\n"
        f"- Primary accuracy, eligible complete raters: {pct(data['primary_familiar_complete'])}\n"
        f"- All submitted ratings: {pct(data['all_responses'])}; chance: 33.3%\n"
        f"- Naive descriptive Wilson 95% interval (primary): {data['primary_familiar_complete']['naive_wilson_95']}\n"
        f"- Per character: {data['per_character']}\n- Confusion matrix (true rows): {data['confusion_matrix']}\n"
        f"- Per rater: {data['per_rater']}\n- Familiarity distribution: {data['familiarity_distribution']}\n"
        f"- Mean confidence, correct / incorrect: {data['mean_confidence_correct']} / {data['mean_confidence_incorrect']}\n"
        f"- Pairwise agreement: {data['agreement']}\n- Responses per scenario: {data['responses_per_scenario']}\n"
        f"- Manual review approved: {data['review']['timestamp']} by {data['review']['reviewer_id']}\n\n"
        f"{data['limitations']} Missing judgments are not counted as incorrect. Familiarity and confidence are distinct from recognition. Persona hashes record operational provenance, not proof against tampering.\n")
