"""Download the public-domain Hercule Poirot corpus from Project Gutenberg."""

import hashlib
import json
import re
from pathlib import Path

import requests


SOURCES = [
    {
        "title": "The Mysterious Affair at Styles",
        "id": 863,
        "url": "https://www.gutenberg.org/cache/epub/863/pg863.txt",
    },
    {
        "title": "Poirot Investigates",
        "id": 61262,
        "url": "https://www.gutenberg.org/cache/epub/61262/pg61262.txt",
    },
    {
        "title": "The Murder on the Links",
        "id": 58866,
        "url": "https://www.gutenberg.org/cache/epub/58866/pg58866.txt",
    },
    {
        "title": "The Murder of Roger Ackroyd",
        "id": 69087,
        "url": "https://www.gutenberg.org/cache/epub/69087/pg69087.txt",
    },
    {
        "title": "The Big Four",
        "id": 70114,
        "url": "https://www.gutenberg.org/cache/epub/70114/pg70114.txt",
    },
    {
        "title": "The Mystery of the Blue Train",
        "id": 72824,
        "url": "https://www.gutenberg.org/cache/epub/72824/pg72824.txt",
    },
    {
        "title": "The Missing Will",
        "id": 67173,
        "url": "https://www.gutenberg.org/cache/epub/67173/pg67173.txt",
    },
    {
        "title": "The Hunter's Lodge Case",
        "id": 67160,
        "url": "https://www.gutenberg.org/cache/epub/67160/pg67160.txt",
    },
    {
        "title": "The Plymouth Express Affair",
        "id": 66446,
        "url": "https://www.gutenberg.org/cache/epub/66446/pg66446.txt",
    },
]

CHARACTER_DIRECTORY = Path(__file__).resolve().parent
RAW_DIRECTORY = CHARACTER_DIRECTORY / "raw"
METADATA_DIRECTORY = CHARACTER_DIRECTORY / "metadata"
METADATA_PATH = METADATA_DIRECTORY / "poirot_sources.json"


def filename_for(source: dict) -> str:
    """Build a stable, filesystem-safe filename for a source."""

    slug = re.sub(r"[^a-z0-9]+", "_", source["title"].lower()).strip("_")
    return f"{source['id']}_{slug}.txt"


def main() -> None:
    RAW_DIRECTORY.mkdir(parents=True, exist_ok=True)
    METADATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

    metadata = []

    with requests.Session() as session:
        session.headers["User-Agent"] = (
            "multi-agent-fictional-personalities/1.0 "
            "(academic corpus downloader)"
        )

        for source in SOURCES:
            print(f"Downloading {source['title']}...")
            response = session.get(source["url"], timeout=30)
            response.raise_for_status()

            text = response.text
            path = RAW_DIRECTORY / filename_for(source)
            path.write_text(text, encoding="utf-8")

            metadata.append(
                {
                    **source,
                    "local_path": str(path.relative_to(CHARACTER_DIRECTORY)),
                    "sha256": hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest(),
                    "source": "Project Gutenberg",
                    "format": "Plain Text UTF-8",
                }
            )

    METADATA_PATH.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Downloaded {len(metadata)} sources.")
    print(f"Metadata saved to: {METADATA_PATH}")


if __name__ == "__main__":
    main()
