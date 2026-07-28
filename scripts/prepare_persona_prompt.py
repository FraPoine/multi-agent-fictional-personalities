"""Prepare the existing Poirot persona-extraction development artifacts."""

import json
from collections import Counter
from pathlib import Path

from multi_agent_personalities.persona_extraction import prepare_persona_prompt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = (
    PROJECT_ROOT
    / "characters"
    / "poirot"
    / "corpus"
    / "persona_corpus.jsonl"
)
PROMPT_TEMPLATE_PATH = PROJECT_ROOT / "prompts" / "extract_persona.md"
OUTPUT_DIRECTORY = PROJECT_ROOT / "outputs" / "poirot"
OUTPUT_PROMPT_PATH = OUTPUT_DIRECTORY / "poirot_persona_prompt.txt"
OUTPUT_EXAMPLES_PATH = (
    OUTPUT_DIRECTORY / "persona_extraction_examples.jsonl"
)

CHARACTER_NAME = "Hercule Poirot"
CHARACTER_DESCRIPTION = (
    "A fictional Belgian private detective known for psychological insight, "
    "method and order, attention to detail, politeness, confidence, vanity, "
    "and frequent French expressions."
)


def write_jsonl(path: Path, records: list[dict]) -> None:
    """Write selected examples as UTF-8 JSONL."""

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def print_summary(records: list[dict]) -> None:
    """Print source and trait coverage."""

    source_counts = Counter(record["source"] for record in records)
    trait_counts = Counter(
        trait for record in records for trait in record["traits"]
    )
    print(f"Selected examples: {len(records)}")
    print("\nExamples by source:")
    for source, count in sorted(source_counts.items()):
        print(f"- {source}: {count}")
    print("\nExamples by trait:")
    for trait, count in sorted(trait_counts.items()):
        print(f"- {trait}: {count}")


def main() -> None:
    compiled_prompt, selected_records = prepare_persona_prompt(
        corpus_path=CORPUS_PATH,
        prompt_template_path=PROMPT_TEMPLATE_PATH,
        character_name=CHARACTER_NAME,
        character_description=CHARACTER_DESCRIPTION,
    )
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    OUTPUT_PROMPT_PATH.write_text(compiled_prompt, encoding="utf-8")
    write_jsonl(OUTPUT_EXAMPLES_PATH, selected_records)

    print_summary(selected_records)
    print()
    print(f"Prompt saved to: {OUTPUT_PROMPT_PATH}")
    print(f"Examples saved to: {OUTPUT_EXAMPLES_PATH}")


if __name__ == "__main__":
    main()
