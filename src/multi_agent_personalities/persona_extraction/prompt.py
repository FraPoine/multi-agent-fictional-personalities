"""Prepare persona-extraction prompts from processed JSONL corpora."""

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Sequence


MIN_CONFIDENCE = 0.85
EXAMPLES_PER_SOURCE = 2
MIN_EXAMPLES_PER_TRAIT = 3
TARGET_TOTAL_EXAMPLES = 50
RANDOM_SEED = 42


def load_jsonl(path: Path) -> list[dict]:
    """Load and validate one processed persona corpus file."""

    if not path.is_file():
        raise FileNotFoundError(f"Persona corpus file not found: {path}")

    records = []
    required_fields = {"id", "source", "text", "traits"}

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON at line {line_number} in {path}: {error}"
                ) from error

            missing_fields = required_fields - record.keys()
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise ValueError(
                    f"Missing fields at line {line_number} in {path}: {missing}"
                )

            if not isinstance(record["traits"], list):
                raise ValueError(
                    f"'traits' must be a list at line {line_number} in {path}"
                )

            if record.get("confidence", 1.0) >= MIN_CONFIDENCE:
                records.append(record)

    return records


def load_corpora(paths: Path | Sequence[Path]) -> list[dict]:
    """Load one or more JSONL corpora in deterministic path order."""

    resolved_paths = (paths,) if isinstance(paths, Path) else tuple(paths)
    if not resolved_paths:
        raise ValueError("At least one persona corpus path is required")

    records: list[dict] = []
    seen_ids: set[str] = set()
    for path in sorted(resolved_paths, key=lambda item: str(item)):
        for record in load_jsonl(path):
            if record["id"] in seen_ids:
                raise ValueError(
                    f"Duplicate corpus record id across files: {record['id']}"
                )
            records.append(record)
            seen_ids.add(record["id"])
    return records


def _rank_candidates(
    candidates: list[dict],
    random_generator: random.Random,
) -> list[dict]:
    ranked = candidates.copy()
    random_generator.shuffle(ranked)
    ranked.sort(
        key=lambda record: record.get("confidence", 0.0),
        reverse=True,
    )
    return ranked


def select_examples(records: list[dict]) -> list[dict]:
    """Select examples with deterministic source and trait coverage."""

    random_generator = random.Random(RANDOM_SEED)
    records_by_source: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        records_by_source[record["source"]].append(record)

    selected_records: list[dict] = []
    selected_ids: set[str] = set()

    def add_record(record: dict) -> bool:
        if record["id"] in selected_ids:
            return False
        selected_records.append(record)
        selected_ids.add(record["id"])
        return True

    for source in sorted(records_by_source):
        candidates = _rank_candidates(
            records_by_source[source],
            random_generator,
        )
        added_for_source = 0
        for candidate in candidates:
            if add_record(candidate):
                added_for_source += 1
            if added_for_source >= EXAMPLES_PER_SOURCE:
                break

    all_traits = sorted(
        {
            trait
            for record in records
            for trait in record["traits"]
        }
    )
    for trait in all_traits:
        current_count = sum(
            trait in record["traits"] for record in selected_records
        )
        missing_count = max(0, MIN_EXAMPLES_PER_TRAIT - current_count)
        candidates = _rank_candidates(
            [
                record
                for record in records
                if trait in record["traits"]
                and record["id"] not in selected_ids
            ],
            random_generator,
        )
        for candidate in candidates[:missing_count]:
            add_record(candidate)

    remaining_records = _rank_candidates(
        [
            record
            for record in records
            if record["id"] not in selected_ids
        ],
        random_generator,
    )
    for record in remaining_records:
        if len(selected_records) >= TARGET_TOTAL_EXAMPLES:
            break
        add_record(record)

    selected_records.sort(
        key=lambda record: (record["source"], record["id"])
    )
    return selected_records


def format_corpus_examples(records: list[dict]) -> str:
    """Format selected corpus passages for the extraction prompt."""

    formatted_examples = []
    for index, record in enumerate(records, start=1):
        formatted_examples.append(
            "\n".join(
                [
                    f"### Example {index}",
                    f"Source: {record['source']}",
                    f"Traits: {', '.join(record['traits'])}",
                    f"Context: {record.get('context', 'Not provided')}",
                    "Confidence: "
                    f"{record.get('confidence', 'Not provided')}",
                    "Text:",
                    record["text"],
                ]
            )
        )
    return "\n\n".join(formatted_examples)


def build_prompt(
    template: str,
    corpus_examples: str,
    *,
    character_name: str,
    character_description: str,
) -> str:
    """Replace the character and corpus placeholders in the prompt."""

    replacements = {
        "{character_name}": character_name,
        "{character_description}": character_description,
        "{corpus_examples}": corpus_examples,
    }
    prompt = template
    for placeholder, value in replacements.items():
        if placeholder not in prompt:
            raise ValueError(
                f"Missing placeholder in template: {placeholder}"
            )
        prompt = prompt.replace(placeholder, value)
    return prompt


def prepare_persona_prompt(
    *,
    corpus_path: Path | Sequence[Path],
    prompt_template_path: Path,
    character_name: str,
    character_description: str,
) -> tuple[str, list[dict]]:
    """Load the corpus and template and return a compiled prompt."""

    records = load_corpora(corpus_path)
    if not records:
        raise ValueError(f"The persona corpus is empty: {corpus_path}")
    if not prompt_template_path.is_file():
        raise FileNotFoundError(
            f"Persona-extraction prompt file not found: "
            f"{prompt_template_path}"
        )

    selected_records = select_examples(records)
    corpus_examples = format_corpus_examples(selected_records)
    template = prompt_template_path.read_text(encoding="utf-8")
    return (
        build_prompt(
            template,
            corpus_examples,
            character_name=character_name,
            character_description=character_description,
        ),
        selected_records,
    )
