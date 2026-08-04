"""Atomic pilot publication and consistent response/analysis persistence."""

from collections.abc import Sequence
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import tempfile

from pydantic import ValidationError

from multi_agent_personalities.evaluation.analysis import analyze_pilot
from multi_agent_personalities.models import (
    EvaluationTrial,
    PublicEvaluationTrial,
    RaterResponse,
    TrialAnswer,
)
from multi_agent_personalities.models.identifiers import validate_run_id


ARTIFACTS = (
    "pilot_manifest.json",
    "trials_public.jsonl",
    "answer_key.jsonl",
    "responses.jsonl",
    "synthetic_responses.jsonl",
    "analysis.json",
    "report.md",
)


def _jsonl(items: Sequence[object]) -> str:
    return "".join(item.model_dump_json() + "\n" for item in items)


def load_jsonl(path: Path, model: type) -> list:
    """Load every nonblank JSONL record; malformed lines fail loudly."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"cannot read pilot artifact {path.name}: {error}") from error
    records = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append(model.model_validate_json(line))
        except (ValidationError, ValueError) as error:
            raise ValueError(
                f"malformed {path.name} record at line {line_number}"
            ) from error
    return records


def _validated_inputs(pilot_directory: Path) -> tuple[list, list]:
    trials = load_jsonl(
        pilot_directory / "trials_public.jsonl", PublicEvaluationTrial
    )
    answers = load_jsonl(pilot_directory / "answer_key.jsonl", TrialAnswer)
    trial_ids = [item.trial_id for item in trials]
    answer_ids = [item.trial_id for item in answers]
    if len(set(trial_ids)) != len(trial_ids):
        raise ValueError("duplicated public trial ID")
    if len(set(answer_ids)) != len(answer_ids):
        raise ValueError("duplicated private answer/provenance record")
    provenance = [
        (item.source_run_id, item.source_message_id) for item in answers
    ]
    if len(set(provenance)) != len(provenance):
        raise ValueError("duplicated private answer/provenance record")
    if set(trial_ids) != set(answer_ids):
        raise ValueError("private records do not match the public trial set")
    return trials, answers


def _validate_responses(
    trials: Sequence[PublicEvaluationTrial], responses: Sequence[RaterResponse]
) -> None:
    trial_map = {item.trial_id: item for item in trials}
    response_ids: set[str] = set()
    rater_trials: set[tuple[str, str]] = set()
    for response in responses:
        if response.response_id in response_ids:
            raise ValueError("duplicated response ID")
        response_ids.add(response.response_id)
        if response.trial_id not in trial_map:
            raise ValueError("unknown trial ID")
        if (
            response.selected_character_id
            not in trial_map[response.trial_id].candidate_character_ids
        ):
            raise ValueError("unsupported candidate selection")
        key = (response.rater_id, response.trial_id)
        if key in rater_trials:
            raise ValueError("duplicated response for rater and trial")
        rater_trials.add(key)


def _validate_global_response_ids(
    human: Sequence[RaterResponse], synthetic: Sequence[RaterResponse]
) -> None:
    all_ids = [item.response_id for item in (*human, *synthetic)]
    if len(set(all_ids)) != len(all_ids):
        raise ValueError("duplicated response ID across response files")


def render_report(
    manifest: dict[str, object], analysis: dict[str, object]
) -> str:
    accuracy = analysis["overall_accuracy"]
    accuracy_text = (
        "not available (no responses)" if accuracy is None else f"{accuracy:.1%}"
    )
    warnings = manifest["trial_generation"]["duplicate_text_warnings"]
    return (
        "# Technical Mock Evaluation Pilot\n\n"
        f"> **{analysis['disclaimer']}**\n\n"
        f"- Pilot ID: `{manifest['pilot_id']}`\n"
        f"- Response source analyzed: {analysis['response_source']}\n"
        f"- Source runs: {', '.join(manifest['source_run_ids'])}\n"
        f"- Trials: {manifest['trial_count']} (one per character per topic)\n"
        f"- Responses: {analysis['total_response_count']}\n"
        f"- Accuracy: {accuracy_text}\n"
        "- Chance baseline: 50%\n"
        "- 95% interval: Wilson score\n"
        f"- Duplicate-text warning groups: {len(warnings)}\n\n"
        "Mock repetition and synthetic responses are development fixtures only.\n"
    )


def _replace_text(path: Path, content: str) -> None:
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


@contextmanager
def _pilot_lock(pilot_directory: Path):
    lock_path = pilot_directory / ".responses.lock"
    with lock_path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def save_pilot(
    *, output_root: Path, pilot_id: str,
    trials: Sequence[EvaluationTrial], manifest: dict[str, object]
) -> Path:
    """Atomically publish a complete new pilot directory."""
    validate_run_id(pilot_id)
    parent = Path(output_root) / "evaluation" / "pilots"
    parent.mkdir(parents=True, exist_ok=True)
    final = parent / pilot_id
    lock = parent / f".{pilot_id}.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise FileExistsError(f"pilot is already reserved: {final}") from error
    os.close(fd)
    temporary: Path | None = None
    try:
        if final.exists():
            raise FileExistsError(f"pilot already exists: {final}")
        temporary = Path(tempfile.mkdtemp(prefix=f".{pilot_id}.", dir=parent))
        public = [
            PublicEvaluationTrial.model_validate(item.public_dict())
            for item in trials
        ]
        answers = [
            TrialAnswer(
                trial_id=item.trial_id,
                correct_character_id=item.correct_character_id,
                source_run_id=item.source_run_id,
                source_message_id=item.source_message_id,
            )
            for item in trials
        ]
        analysis = analyze_pilot(public, answers, [], response_source="human")
        files = {
            "pilot_manifest.json": json.dumps(manifest, indent=2) + "\n",
            "trials_public.jsonl": _jsonl(public),
            "answer_key.jsonl": _jsonl(answers),
            "responses.jsonl": "",
            "synthetic_responses.jsonl": "",
            "analysis.json": json.dumps(analysis, indent=2) + "\n",
            "report.md": render_report(manifest, analysis),
        }
        for name, content in files.items():
            (temporary / name).write_text(content, encoding="utf-8")
        temporary.rename(final)
    except BaseException:
        if temporary is not None:
            shutil.rmtree(temporary, ignore_errors=True)
        raise
    finally:
        lock.unlink(missing_ok=True)
    return final


def refresh_analysis(
    pilot_directory: Path, *, response_source: str = "human"
) -> dict[str, object]:
    """Explicitly analyze either genuine or development-only responses."""
    if response_source not in {"human", "synthetic"}:
        raise ValueError("response_source must be 'human' or 'synthetic'")
    directory = Path(pilot_directory)
    with _pilot_lock(directory):
        trials, answers = _validated_inputs(directory)
        filename = (
            "responses.jsonl"
            if response_source == "human"
            else "synthetic_responses.jsonl"
        )
        responses = load_jsonl(directory / filename, RaterResponse)
        _validate_responses(trials, responses)
        other_filename = (
            "synthetic_responses.jsonl"
            if response_source == "human"
            else "responses.jsonl"
        )
        other = load_jsonl(directory / other_filename, RaterResponse)
        _validate_responses(trials, other)
        _validate_global_response_ids(
            responses if response_source == "human" else other,
            other if response_source == "human" else responses,
        )
        analysis = analyze_pilot(
            trials, answers, responses, response_source=response_source
        )
        manifest = json.loads(
            (directory / "pilot_manifest.json").read_text(encoding="utf-8")
        )
        _replace_text(
            directory / "analysis.json", json.dumps(analysis, indent=2) + "\n"
        )
        _replace_text(directory / "report.md", render_report(manifest, analysis))
        return analysis


def submit_rater_response(
    pilot_directory: Path, response: RaterResponse
) -> dict[str, object]:
    """Commit one genuine response and matching analysis under one lock."""
    if response.synthetic_data:
        raise ValueError("rater submissions cannot be marked synthetic")
    directory = Path(pilot_directory)
    with _pilot_lock(directory):
        trials, answers = _validated_inputs(directory)
        existing = load_jsonl(directory / "responses.jsonl", RaterResponse)
        updated = [*existing, response]
        _validate_responses(trials, updated)
        synthetic = load_jsonl(
            directory / "synthetic_responses.jsonl", RaterResponse
        )
        _validate_responses(trials, synthetic)
        _validate_global_response_ids(updated, synthetic)
        analysis = analyze_pilot(
            trials, answers, updated, response_source="human"
        )
        manifest = json.loads(
            (directory / "pilot_manifest.json").read_text(encoding="utf-8")
        )
        # All content is validated and rendered before any canonical replacement.
        response_text = _jsonl(updated)
        analysis_text = json.dumps(analysis, indent=2) + "\n"
        report_text = render_report(manifest, analysis)
        response_path = directory / "responses.jsonl"
        analysis_path = directory / "analysis.json"
        report_path = directory / "report.md"
        originals = {
            response_path: response_path.read_text(encoding="utf-8"),
            analysis_path: analysis_path.read_text(encoding="utf-8"),
            report_path: report_path.read_text(encoding="utf-8"),
        }
        replaced: list[Path] = []
        try:
            for path, content in (
                (response_path, response_text),
                (analysis_path, analysis_text),
                (report_path, report_text),
            ):
                _replace_text(path, content)
                replaced.append(path)
        except BaseException:
            for path in reversed(replaced):
                _replace_text(path, originals[path])
            raise
        return analysis


def save_synthetic_responses(
    pilot_directory: Path, responses: Sequence[RaterResponse]
) -> dict[str, object]:
    """Save and analyze an explicit development-only response set."""
    if not responses or any(not item.synthetic_data for item in responses):
        raise ValueError("synthetic response sets must be nonempty and fully synthetic")
    directory = Path(pilot_directory)
    with _pilot_lock(directory):
        trials, answers = _validated_inputs(directory)
        _validate_responses(trials, responses)
        human = load_jsonl(directory / "responses.jsonl", RaterResponse)
        _validate_responses(trials, human)
        _validate_global_response_ids(human, responses)
        analysis = analyze_pilot(
            trials, answers, responses, response_source="synthetic"
        )
        manifest_path = directory / "pilot_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["synthetic_responses_created"] = True
        _replace_text(directory / "synthetic_responses.jsonl", _jsonl(responses))
        _replace_text(manifest_path, json.dumps(manifest, indent=2) + "\n")
        _replace_text(
            directory / "analysis.json", json.dumps(analysis, indent=2) + "\n"
        )
        _replace_text(directory / "report.md", render_report(manifest, analysis))
        return analysis
