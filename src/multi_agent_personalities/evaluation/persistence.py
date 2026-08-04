"""Atomic pilot publication and validated response persistence."""

import json
import os
import shutil
import tempfile
from pathlib import Path
from collections.abc import Sequence

from multi_agent_personalities.evaluation.analysis import analyze_pilot
from multi_agent_personalities.models import EvaluationTrial, PublicEvaluationTrial, RaterResponse, TrialAnswer
from multi_agent_personalities.models.identifiers import validate_run_id


ARTIFACTS = ("pilot_manifest.json", "trials_public.jsonl", "answer_key.jsonl", "responses.jsonl", "analysis.json", "report.md")


def _jsonl(items: Sequence[object]) -> str:
    return "".join(item.model_dump_json() + "\n" for item in items)


def render_report(manifest: dict[str, object], analysis: dict[str, object]) -> str:
    disclaimer = analysis["disclaimer"]
    accuracy = analysis["overall_accuracy"]
    accuracy_text = "not available (no responses)" if accuracy is None else f"{accuracy:.1%}"
    warnings = manifest["trial_generation"]["duplicate_text_warnings"]
    return (
        "# Technical Mock Evaluation Pilot\n\n"
        f"> **{disclaimer}**\n\n"
        f"- Pilot ID: `{manifest['pilot_id']}`\n"
        f"- Source runs: {', '.join(manifest['source_run_ids'])}\n"
        f"- Trials: {manifest['trial_count']} (balanced across two characters)\n"
        f"- Responses: {analysis['total_response_count']}\n"
        f"- Accuracy: {accuracy_text}\n"
        "- Chance baseline: 50%\n"
        "- 95% interval: Wilson score\n"
        f"- Duplicate-text warning groups: {len(warnings)}\n\n"
        "Mock repetition and synthetic responses, if present, are development fixtures only.\n"
    )


def save_pilot(*, output_root: Path, pilot_id: str, trials: Sequence[EvaluationTrial], manifest: dict[str, object]) -> Path:
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
        public = [PublicEvaluationTrial.model_validate(item.public_dict()) for item in trials]
        answers = [TrialAnswer(trial_id=item.trial_id, correct_character_id=item.correct_character_id) for item in trials]
        analysis = analyze_pilot(public, answers, [])
        files = {
            "pilot_manifest.json": json.dumps(manifest, indent=2) + "\n",
            "trials_public.jsonl": _jsonl(public),
            "answer_key.jsonl": _jsonl(answers),
            "responses.jsonl": "",
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


def load_jsonl(path: Path, model: type) -> list:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"cannot read pilot artifact {path.name}: {error}") from error
    return [model.model_validate_json(line) for line in lines if line.strip()]


def refresh_analysis(pilot_directory: Path) -> dict[str, object]:
    trials = load_jsonl(pilot_directory / "trials_public.jsonl", PublicEvaluationTrial)
    answers = load_jsonl(pilot_directory / "answer_key.jsonl", TrialAnswer)
    responses = load_jsonl(pilot_directory / "responses.jsonl", RaterResponse)
    analysis = analyze_pilot(trials, answers, responses)
    manifest = json.loads((pilot_directory / "pilot_manifest.json").read_text(encoding="utf-8"))
    analysis_path = pilot_directory / "analysis.json"
    report_path = pilot_directory / "report.md"
    for path, content in ((analysis_path, json.dumps(analysis, indent=2) + "\n"), (report_path, render_report(manifest, analysis))):
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=pilot_directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
            Path(temporary_name).replace(path)
        except BaseException:
            Path(temporary_name).unlink(missing_ok=True)
            raise
    return analysis


def append_response(pilot_directory: Path, response: RaterResponse) -> None:
    trials = load_jsonl(pilot_directory / "trials_public.jsonl", PublicEvaluationTrial)
    trial_map = {item.trial_id: item for item in trials}
    if response.trial_id not in trial_map:
        raise ValueError("unknown trial")
    if response.selected_character_id not in trial_map[response.trial_id].candidate_character_ids:
        raise ValueError("unsupported character selection")
    path = pilot_directory / "responses.jsonl"
    lock = pilot_directory / ".responses.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RuntimeError("responses are currently being updated") from error
    os.close(fd)
    try:
        existing = load_jsonl(path, RaterResponse)
        if any(item.rater_id == response.rater_id and item.trial_id == response.trial_id for item in existing):
            raise ValueError("this rater already answered this trial")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(response.model_dump_json() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        lock.unlink(missing_ok=True)
