import json
from pathlib import Path


CORPUS_DIRECTORY = Path("characters/sherlock/corpus")
CORPUS_FILENAME = "sherlock_holmes_corpus_all.jsonl"
CORPUS_PATH = CORPUS_DIRECTORY / CORPUS_FILENAME


def load_corpus(path: Path) -> list[dict]:
    passages = []

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                passage = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON at line {line_number}: {error}"
                ) from error

            passages.append(passage)

    return passages


if __name__ == "__main__":
    corpus = load_corpus(CORPUS_PATH)
    print(f"Loaded {len(corpus)} Sherlock passages.")