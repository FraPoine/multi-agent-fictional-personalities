# scripts/download_sherlock.py
from pathlib import Path
import hashlib
import json
import requests

SOURCES = [
    {"title": "A Study in Scarlet", "id": 244, "url": "https://www.gutenberg.org/ebooks/244.txt.utf-8"},
    {"title": "The Sign of the Four", "id": 2097, "url": "https://www.gutenberg.org/ebooks/2097.txt.utf-8"},
    {"title": "The Adventures of Sherlock Holmes", "id": 1661, "url": "https://www.gutenberg.org/ebooks/1661.txt.utf-8"},
    {"title": "The Memoirs of Sherlock Holmes", "id": 834, "url": "https://www.gutenberg.org/ebooks/834.txt.utf-8"},
    {"title": "The Hound of the Baskervilles", "id": 2852, "url": "https://www.gutenberg.org/ebooks/2852.txt.utf-8"},
    {"title": "The Return of Sherlock Holmes", "id": 108, "url": "https://www.gutenberg.org/ebooks/108.txt.utf-8"},
    {"title": "The Valley of Fear", "id": 3289, "url": "https://www.gutenberg.org/ebooks/3289.txt.utf-8"},
    {"title": "His Last Bow", "id": 2350, "url": "https://www.gutenberg.org/ebooks/2350.txt.utf-8"},
    {"title": "The Case-Book of Sherlock Holmes", "id": 69700, "url": "https://www.gutenberg.org/ebooks/69700.txt.utf-8"},
]

RAW_DIR = Path("./raw")
META_DIR = Path("./metadata")
RAW_DIR.mkdir(parents=True, exist_ok=True)
META_DIR.mkdir(parents=True, exist_ok=True)

metadata = []

for source in SOURCES:
    print(f"Downloading {source['title']}...")
    response = requests.get(source["url"], timeout=30)
    response.raise_for_status()

    text = response.text
    filename = f"{source['id']}_{source['title'].lower().replace(' ', '_').replace(':', '')}.txt"
    path = RAW_DIR / filename
    path.write_text(text, encoding="utf-8")

    metadata.append({
        **source,
        "local_path": str(path),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source": "Project Gutenberg",
        "format": "Plain Text UTF-8",
    })

(META_DIR / "sherlock_sources.json").write_text(
    json.dumps(metadata, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print("Done.")