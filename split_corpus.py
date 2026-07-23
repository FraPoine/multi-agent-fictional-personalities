import json
import random
from collections import defaultdict
from pathlib import Path


CORPUS_DIRECTORY = Path("characters/sherlock/corpus")

INPUT_FILENAME = "sherlock_holmes_corpus_all.jsonl"
PERSONA_FILENAME = "persona_corpus.jsonl"
EVALUATION_FILENAME = "evaluation_corpus.jsonl"

INPUT_PATH = CORPUS_DIRECTORY / INPUT_FILENAME
PERSONA_OUTPUT_PATH = CORPUS_DIRECTORY / PERSONA_FILENAME
EVALUATION_OUTPUT_PATH = CORPUS_DIRECTORY / EVALUATION_FILENAME

EVALUATION_RATIO = 0.20
RANDOM_SEED = 42


def load_jsonl(path: Path) -> list[dict]:
    records = []

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

            if "source" not in record:
                raise ValueError(
                    f"Missing 'source' field at line {line_number}"
                )

            records.append(record)

    return records


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            json_line = json.dumps(record, ensure_ascii=False)
            file.write(json_line + "\n")


def split_corpus_by_source(
    records: list[dict],
) -> tuple[list[dict], list[dict]]:
    records_by_source = defaultdict(list)

    for record in records:
        records_by_source[record["source"]].append(record)

    random_generator = random.Random(RANDOM_SEED)

    persona_records = []
    evaluation_records = []

    for source in sorted(records_by_source):
        source_records = records_by_source[source].copy()
        random_generator.shuffle(source_records)

        total = len(source_records)

        if total < 2:
            evaluation_count = 0
        else:
            evaluation_count = round(total * EVALUATION_RATIO)
            evaluation_count = max(1, evaluation_count)
            evaluation_count = min(total - 1, evaluation_count)

        evaluation_records.extend(
            source_records[:evaluation_count]
        )

        persona_records.extend(
            source_records[evaluation_count:]
        )

        print(
            f"{source}: "
            f"{total - evaluation_count} persona, "
            f"{evaluation_count} evaluation"
        )

    return persona_records, evaluation_records


def main() -> None:
    corpus = load_jsonl(INPUT_PATH)

    persona_corpus, evaluation_corpus = split_corpus_by_source(
        corpus
    )

    write_jsonl(PERSONA_OUTPUT_PATH, persona_corpus)
    write_jsonl(EVALUATION_OUTPUT_PATH, evaluation_corpus)

    print()
    print(f"Total passages: {len(corpus)}")
    print(f"Persona passages: {len(persona_corpus)}")
    print(f"Evaluation passages: {len(evaluation_corpus)}")


if __name__ == "__main__":
    main()