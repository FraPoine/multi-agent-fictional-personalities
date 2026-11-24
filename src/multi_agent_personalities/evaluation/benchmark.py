"""Strict offline import and blind-trial construction for the development benchmark.

All generated records other than trials_public.jsonl are private research artifacts.
"""
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

import yaml
from pydantic import BaseModel, ConfigDict, Field

from multi_agent_personalities.evaluation.config import load_three_persona_benchmark_config
from multi_agent_personalities.models import ConversationRun, Message
from multi_agent_personalities.models.identifiers import validate_run_id

IDS = {"sherlock": "sherlock_holmes", "poirot": "hercule_poirot", "layton": "professor_layton"}
ALIASES = re.compile(r"\b(?:sherlock(?:\s+holmes)?|holmes|hercule(?:\s+poirot)?|poirot|(?:professor\s+)?(?:hershel\s+)?layton|hershel)\b", re.I)
SELF = re.compile(r"\b(?:i\s+am|i'm|my\s+name\s+is|call\s+me|this\s+is)\s+(?:(?:the|professor|detective|mr\.?|monsieur)\s+)?(?:sherlock|holmes|hercule|poirot|hershel|layton)\b", re.I)
OWN_NAMES = {
    "sherlock_holmes": re.compile(r"\b(?:sherlock|holmes)\b", re.I),
    "hercule_poirot": re.compile(r"\b(?:hercule|poirot)\b", re.I),
    "professor_layton": re.compile(r"\b(?:hershel|layton)\b", re.I),
}
METADATA = re.compile(r"(?:\b(?:source_run_id|source_message_id|speaker_character_id|persona_path|prompt_template_sha256)\b|(?:[A-Za-z]:\\|/)(?:[^\s/\\]+[/\\]){1,}[^\s]+|\bhttps?://\S+)", re.I)


class PublicBenchmarkTrial(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    trial_id: str = Field(pattern=r"^trial_[0-9a-f]{32}$")
    display_text: str = Field(min_length=1)
    candidate_character_ids: tuple[str, str, str]


class _UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError(f"duplicate manifest key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _read_sources(path, scenarios):
    try:
        data = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=_UniqueLoader)
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"invalid source manifest: {error}") from error
    if not isinstance(data, dict) or set(data) != {"sources"} or not isinstance(data["sources"], dict):
        raise ValueError("manifest must contain only a sources mapping")
    sources = data["sources"]
    if set(sources) != {item.id for item in scenarios}:
        raise ValueError("manifest must map exactly the six configured scenarios")
    for value in sources.values():
        validate_run_id(value)
    if len(set(sources.values())) != 6:
        raise ValueError("source run IDs must be distinct")
    return sources


def _load_run(directory, run_id):
    try:
        raw = (directory / "run.json").read_bytes()
        lines = (directory / "messages.jsonl").read_bytes()
        run = ConversationRun.model_validate_json(raw)
        messages = tuple(Message.model_validate_json(line) for line in lines.splitlines() if line.strip())
    except (OSError, ValueError) as error:
        raise ValueError(f"invalid source run {run_id}: {error}") from error
    if run.run_id != run_id or messages != run.messages:
        raise ValueError(f"source run {run_id} has inconsistent artifact records")
    return run, {"run.json": sha256(raw).hexdigest(), "messages.jsonl": sha256(lines).hexdigest()}


def _validate_run(run, scenario, config):
    order = tuple(IDS[slug] for slug in scenario.speaker_order)
    if (run.topic != scenario.topic or run.character_ids != order or run.turn_count != 6
            or run.status != "completed" or run.provider != "copilot"
            or run.prompt_variant != config.prompt_variant
            or run.prompt_template_sha256 != config.prompt_template_sha256):
        raise ValueError(f"source run {run.run_id} does not match scenario configuration")
    if run.model != config.model or run.configured_model != config.model:
        raise ValueError(f"source run {run.run_id} does not match the explicit configured model")
    if run.persona_sources is None:
        raise ValueError(f"source run {run.run_id} lacks generation-time persona provenance")
    for slug, source in zip(scenario.speaker_order, run.persona_sources):
        expected = config.personas[slug]
        if source.character_id != IDS[slug] or source.path != expected.path or source.sha256 != expected.sha256:
            raise ValueError(f"source run {run.run_id} has incompatible persona provenance")
    for i, msg in enumerate(run.messages):
        if msg.speaker_character_id != order[i % 3] or msg.provider != "copilot" or msg.model != run.model:
            raise ValueError(f"source run {run.run_id} has inconsistent message order or metadata")


def _anonymize(text, run, speaker):
    if not text.strip():
        return None, "empty_text", 0
    if SELF.search(text) or OWN_NAMES[speaker].search(text):
        return None, "self_identification", 0
    if METADATA.search(text) or any(value and value in text for value in (run.run_id, *(m.message_id for m in run.messages), *(p.path for p in run.persona_sources))):
        return None, "source_metadata", 0
    # Only an initial direct address is masked: other name uses may carry
    # substantive facts and cannot be changed safely without interpretation.
    masked, count = re.subn(r"^(?:\s*)(?:dear\s+)?(?:sherlock(?:\s+holmes)?|holmes|hercule(?:\s+poirot)?|poirot|(?:professor\s+)?(?:hershel\s+)?layton|hershel)(?=\s*,)", "[name]", text.strip(), count=1, flags=re.I)
    if ALIASES.search(masked):
        return None, "unsafe_name_reference", 0
    return masked, None, count


def prepare_three_persona_benchmark(*, source_manifest: Path, output_root: Path, config_path: Path) -> Path:
    """Validate sources, select second turns with first-turn fallback, publish atomically."""
    config = load_three_persona_benchmark_config(config_path)
    sources = _read_sources(source_manifest, config.scenarios)
    runs = []
    checksums = {}
    for scenario in config.scenarios:
        run_id = sources[scenario.id]
        run, hashes = _load_run(Path(output_root) / "conversations" / "runs" / run_id, run_id)
        _validate_run(run, scenario, config)
        runs.append(run)
        checksums[scenario.id] = {"run_id": run_id, "sha256": hashes}
    if len({run.model for run in runs}) != 1:
        raise ValueError("all source runs must use the same explicit model")
    public, answers, review = [], [], []
    used_text = set()
    for scenario, run in zip(config.scenarios, runs):
        for slug in scenario.speaker_order:
            character = IDS[slug]
            messages = [msg for msg in run.messages if msg.speaker_character_id == character]
            if len(messages) != 2:
                raise ValueError("source must have exactly two messages per character")
            selected = None
            for msg in reversed(messages):
                if msg.error:
                    display, reason, masked = None, "generation_error", 0
                else:
                    display, reason, masked = _anonymize(msg.text, run, character)
                if display and display.casefold() in used_text:
                    display, reason = None, "duplicate_text"
                if reason:
                    review.append({"scenario_id": scenario.id, "run_id": run.run_id, "message_id": msg.message_id, "decision": "excluded", "reason": reason})
                    continue
                selected = (msg, display, masked)
                break
            if selected is None:
                raise ValueError(f"no eligible message for {character} in {scenario.id}; review required")
            msg, display, masked = selected
            used_text.add(display.casefold())
            trial_id = "trial_" + sha256(f"{config.id}\x1f{run.run_id}\x1f{msg.message_id}".encode()).hexdigest()[:32]
            public.append(PublicBenchmarkTrial(trial_id=trial_id, display_text=display, candidate_character_ids=tuple(IDS.values())))
            answers.append({"trial_id": trial_id, "correct_character_id": character, "scenario_id": scenario.id, "source_run_id": run.run_id, "source_message_id": msg.message_id, "turn_index": msg.turn_index, "original_text": msg.text, "mask_count": masked})
            review.append({"scenario_id": scenario.id, "run_id": run.run_id, "message_id": msg.message_id, "trial_id": trial_id, "decision": "selected", "mask_count": masked})
    if len(public) != 18 or len({p.trial_id for p in public}) != 18 or Counter(a["correct_character_id"] for a in answers) != Counter({key: 6 for key in IDS.values()}):
        raise ValueError("balanced trial validation failed")
    public.sort(key=lambda p: p.trial_id)
    answers.sort(key=lambda a: a["trial_id"])
    manifest = {"benchmark_id": config.id, "status": config.status, "model": runs[0].model, "provider": config.provider, "prompt_variant": config.prompt_variant, "prompt_template_sha256": config.prompt_template_sha256, "config_sha256": sha256(Path(config_path).read_bytes()).hexdigest(), "seed": config.seed, "sources": checksums, "trial_count": 18, "personas": {k: v.model_dump() for k, v in config.personas.items()}}
    parent = Path(output_root) / "evaluation" / "benchmarks"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / config.id
    lock = parent / f".{config.id}.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise FileExistsError("benchmark is already reserved") from error
    os.close(fd)
    temporary = None
    try:
        if target.exists():
            raise FileExistsError(f"benchmark already exists: {target}")
        temporary = Path(tempfile.mkdtemp(prefix=f".{config.id}.", dir=parent))
        files = {"benchmark_manifest.json": json.dumps(manifest, indent=2) + "\n", "trials_public.jsonl": "".join(x.model_dump_json() + "\n" for x in public), "answer_key.jsonl": "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in answers), "leakage_review.json": json.dumps({"manual_review_required": True, "decisions": review}, indent=2, ensure_ascii=False) + "\n"}
        for name, content in files.items():
            (temporary / name).write_text(content, encoding="utf-8")
        temporary.rename(target)
    finally:
        if temporary is not None and temporary.exists():
            shutil.rmtree(temporary)
        lock.unlink(missing_ok=True)
    return target
