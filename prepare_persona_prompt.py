import json
import random
from collections import Counter, defaultdict
from pathlib import Path


# Paths
# This script lives in the repository root, so its parent directory is the
# project root. Using parents[1] incorrectly selected the directory above it.
PROJECT_ROOT = Path(__file__).resolve().parent

CORPUS_PATH = (
    PROJECT_ROOT
    / "characters"
    / "sherlock"
    / "corpus"
    / "persona_corpus.jsonl"
)

PROMPT_TEMPLATE_PATH = (
    PROJECT_ROOT
    / "prompts"
    / "extract_persona.md"
)

OUTPUT_DIRECTORY = PROJECT_ROOT / "outputs" / "sherlock"

OUTPUT_PROMPT_PATH = (
    OUTPUT_DIRECTORY / "sherlock_persona_prompt.txt"
)

OUTPUT_EXAMPLES_PATH = (
    OUTPUT_DIRECTORY / "persona_extraction_examples.jsonl"
)


# Character
CHARACTER_NAME = "Sherlock Holmes"

CHARACTER_DESCRIPTION = (
    "A fictional consulting detective known for careful observation, "
    "deductive reasoning, precision, confidence, and emotional restraint."
)


# Selection settings
EXAMPLES_PER_SOURCE = 2
MIN_EXAMPLES_PER_TRAIT = 3
TARGET_TOTAL_EXAMPLES = 50

MIN_CONFIDENCE = 0.85
RANDOM_SEED = 42


def load_jsonl(path: Path) -> list[dict]:
    """Load and validate the JSONL corpus."""

    records = []

    required_fields = {
        "id",
        "source",
        "text",
        "traits",
    }

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON at line {line_number}: {error}"
                ) from error

            missing_fields = required_fields - record.keys()

            if missing_fields:
                missing = ", ".join(sorted(missing_fields))

                raise ValueError(
                    f"Missing fields at line {line_number}: {missing}"
                )

            if not isinstance(record["traits"], list):
                raise ValueError(
                    f"'traits' must be a list at line {line_number}"
                )

            confidence = record.get("confidence", 1.0)

            if confidence >= MIN_CONFIDENCE:
                records.append(record)

    return records


def rank_candidates(
    candidates: list[dict],
    random_generator: random.Random,
) -> list[dict]:
    """
    Randomize records with the same confidence while prioritizing
    high-confidence examples.
    """

    ranked = candidates.copy()
    random_generator.shuffle(ranked)

    ranked.sort(
        key=lambda record: record.get("confidence", 0.0),
        reverse=True,
    )

    return ranked


def select_examples(records: list[dict]) -> list[dict]:
    """
    Select examples ensuring coverage of every source and trait.
    """

    random_generator = random.Random(RANDOM_SEED)

    records_by_source = defaultdict(list)

    for record in records:
        records_by_source[record["source"]].append(record)

    selected_records = []
    selected_ids = set()

    def add_record(record: dict) -> bool:
        record_id = record["id"]

        if record_id in selected_ids:
            return False

        selected_records.append(record)
        selected_ids.add(record_id)

        return True

    # Step 1: select examples from every book
    for source in sorted(records_by_source):
        candidates = rank_candidates(
            records_by_source[source],
            random_generator,
        )

        added_for_source = 0

        for candidate in candidates:
            if add_record(candidate):
                added_for_source += 1

            if added_for_source >= EXAMPLES_PER_SOURCE:
                break

    # Step 2: ensure every trait is sufficiently represented
    all_traits = sorted({
        trait
        for record in records
        for trait in record["traits"]
    })

    for trait in all_traits:
        current_count = sum(
            trait in record["traits"]
            for record in selected_records
        )

        missing_count = max(
            0,
            MIN_EXAMPLES_PER_TRAIT - current_count,
        )

        candidates = [
            record
            for record in records
            if trait in record["traits"]
            and record["id"] not in selected_ids
        ]

        candidates = rank_candidates(
            candidates,
            random_generator,
        )

        for candidate in candidates[:missing_count]:
            add_record(candidate)

    # Step 3: fill until the target number is reached
    remaining_records = [
        record
        for record in records
        if record["id"] not in selected_ids
    ]

    remaining_records = rank_candidates(
        remaining_records,
        random_generator,
    )

    for record in remaining_records:
        if len(selected_records) >= TARGET_TOTAL_EXAMPLES:
            break

        add_record(record)

    selected_records.sort(
        key=lambda record: (
            record["source"],
            record["id"],
        )
    )

    return selected_records


def format_corpus_examples(records: list[dict]) -> str:
    """Format the selected passages for the prompt."""

    formatted_examples = []

    for index, record in enumerate(records, start=1):
        traits = ", ".join(record["traits"])
        context = record.get("context", "Not provided")
        confidence = record.get("confidence", "Not provided")

        formatted_examples.append(
            "\n".join([
                f"### Example {index}",
                f"Source: {record['source']}",
                f"Traits: {traits}",
                f"Context: {context}",
                f"Confidence: {confidence}",
                "Text:",
                record["text"],
            ])
        )

    return "\n\n".join(formatted_examples)


def build_prompt(
    template: str,
    corpus_examples: str,
) -> str:
    """Replace the placeholders in extract_persona.md."""

    replacements = {
        "{character_name}": CHARACTER_NAME,
        "{character_description}": CHARACTER_DESCRIPTION,
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


def write_jsonl(path: Path, records: list[dict]) -> None:
    """Write the selected examples to a JSONL file."""

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )


def print_summary(records: list[dict]) -> None:
    """Print source and trait coverage."""

    source_counts = Counter(
        record["source"]
        for record in records
    )

    trait_counts = Counter(
        trait
        for record in records
        for trait in record["traits"]
    )

    print(f"Selected examples: {len(records)}")

    print("\nExamples by source:")

    for source, count in sorted(source_counts.items()):
        print(f"- {source}: {count}")

    print("\nExamples by trait:")

    for trait, count in sorted(trait_counts.items()):
        print(f"- {trait}: {count}")


def main() -> None:
    records = load_jsonl(CORPUS_PATH)

    if not records:
        raise ValueError("The persona corpus is empty")

    selected_records = select_examples(records)

    corpus_examples = format_corpus_examples(
        selected_records
    )

    prompt_template = PROMPT_TEMPLATE_PATH.read_text(
        encoding="utf-8"
    )

    compiled_prompt = build_prompt(
        prompt_template,
        corpus_examples,
    )

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PROMPT_PATH.write_text(
        compiled_prompt,
        encoding="utf-8",
    )

    write_jsonl(
        OUTPUT_EXAMPLES_PATH,
        selected_records,
    )

    print_summary(selected_records)

    print()
    print(f"Prompt saved to: {OUTPUT_PROMPT_PATH}")
    print(f"Examples saved to: {OUTPUT_EXAMPLES_PATH}")


if __name__ == "__main__":
    main()
