#!/usr/bin/env python3
"""
Clean raw Project Gutenberg text files for the Sherlock Holmes corpus.

This script does NOT extract dialogue yet.
It only prepares clean source text by:
- removing Project Gutenberg header/footer boilerplate
- normalizing line endings and Unicode punctuation
- removing obvious front/back metadata
- fixing hyphenated line breaks
- rebuilding paragraphs from wrapped lines
- writing cleaned .txt files
- writing a manifest with hashes and basic statistics

Recommended repo location:
    scripts/clean_sherlock_raw.py

Default input:
    data/corpora/sherlock/raw/*.txt

Default output:
    data/corpora/sherlock/clean/*.txt
    data/corpora/sherlock/metadata/clean_manifest.json

Usage:
    python scripts/clean_sherlock_raw.py

Or with custom paths:
    python scripts/clean_sherlock_raw.py \
        --input-dir data/corpora/sherlock/raw \
        --output-dir data/corpora/sherlock/clean \
        --manifest data/corpora/sherlock/metadata/clean_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


START_MARKERS = [
    "*** START OF THE PROJECT GUTENBERG EBOOK",
    "*** START OF THIS PROJECT GUTENBERG EBOOK",
]

END_MARKERS = [
    "*** END OF THE PROJECT GUTENBERG EBOOK",
    "*** END OF THIS PROJECT GUTENBERG EBOOK",
]

# We normalize some typography, but we preserve dialogue quotes.
UNICODE_REPLACEMENTS = {
    "\ufeff": "",       # BOM
    "\u00a0": " ",      # non-breaking space
    "\u200b": "",       # zero-width space
    "\r\n": "\n",
    "\r": "\n",
    "—": "—",           # keep em dash, explicit for readability
    "–": "-",           # normalize en dash to hyphen
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
}

# Lines that are usually editorial noise, not story content.
DROP_LINE_PATTERNS = [
    re.compile(r"^\s*Produced by\b", re.IGNORECASE),
    re.compile(r"^\s*Transcribed from\b", re.IGNORECASE),
    re.compile(r"^\s*Updated editions will replace\b", re.IGNORECASE),
    re.compile(r"^\s*Creating the works from print editions\b", re.IGNORECASE),
    re.compile(r"^\s*This file was produced from images\b", re.IGNORECASE),
    re.compile(r"^\s*Character set encoding\b", re.IGNORECASE),
    re.compile(r"^\s*\[Illustration", re.IGNORECASE),
    re.compile(r"^\s*\[Footnote", re.IGNORECASE),
]

# Chapter/story headings are preserved by default because they are useful for traceability.
# If later you want a model-only corpus, remove headings in the extraction script instead.

@dataclass
class CleanStats:
    source_file: str
    output_file: str
    raw_chars: int
    clean_chars: int
    raw_sha256: str
    clean_sha256: str
    estimated_words: int
    estimated_quote_count: int
    gutenberg_start_found: bool
    gutenberg_end_found: bool


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_unicode(text: str) -> str:
    for old, new in UNICODE_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text


def strip_gutenberg_boilerplate(text: str) -> tuple[str, bool, bool]:
    """Return story body and booleans for whether start/end markers were found."""
    upper_text = text.upper()

    start_index = None
    for marker in START_MARKERS:
        idx = upper_text.find(marker)
        if idx != -1:
            # Move to the next line after the marker.
            newline_idx = text.find("\n", idx)
            start_index = newline_idx + 1 if newline_idx != -1 else idx + len(marker)
            break

    end_index = None
    for marker in END_MARKERS:
        idx = upper_text.find(marker)
        if idx != -1:
            end_index = idx
            break

    start_found = start_index is not None
    end_found = end_index is not None

    if start_index is None:
        start_index = 0
    if end_index is None:
        end_index = len(text)

    if end_index < start_index:
        # Defensive fallback: do not accidentally delete the whole book.
        return text, start_found, end_found

    return text[start_index:end_index], start_found, end_found


def drop_noise_lines(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()

        if any(pattern.search(stripped) for pattern in DROP_LINE_PATTERNS):
            continue

        # Drop separator-only lines.
        if re.fullmatch(r"[\s*_\-=~]{3,}", stripped):
            continue

        cleaned_lines.append(line.rstrip())

    return "\n".join(cleaned_lines)


def fix_hyphenated_line_breaks(text: str) -> str:
    """
    Join words split across line breaks, e.g.:
        extraor-\nordinary -> extraordinary

    Conservative rule: only join lowercase/letter fragments.
    """
    return re.sub(r"([A-Za-z])-[ \t]*\n[ \t]*([a-z])", r"\1\2", text)


def rebuild_paragraphs(text: str) -> str:
    """
    Project Gutenberg plain text is often hard-wrapped.
    This function joins wrapped lines into paragraphs while preserving blank-line paragraph breaks.
    """
    paragraphs: list[str] = []
    current: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()

        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue

        current.append(stripped)

    if current:
        paragraphs.append(" ".join(current))

    # Clean repeated spaces inside each paragraph.
    paragraphs = [re.sub(r"[ \t]{2,}", " ", p).strip() for p in paragraphs]

    # Keep one blank line between paragraphs.
    return "\n\n".join(p for p in paragraphs if p)


def final_cleanup(text: str) -> str:
    # Remove spaces before punctuation.
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)

    # Normalize excessive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove leading/trailing whitespace and ensure final newline.
    return text.strip() + "\n"


def estimate_word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def estimate_quote_count(text: str) -> int:
    # Counts pairs of straight double quotes after normalization.
    return text.count('"') // 2


def clean_text(raw_text: str) -> tuple[str, bool, bool]:
    text = normalize_unicode(raw_text)
    text, start_found, end_found = strip_gutenberg_boilerplate(text)
    text = drop_noise_lines(text)
    text = fix_hyphenated_line_breaks(text)
    text = rebuild_paragraphs(text)
    text = final_cleanup(text)
    return text, start_found, end_found


def iter_text_files(input_dir: Path) -> Iterable[Path]:
    yield from sorted(input_dir.glob("*.txt"))


def clean_file(input_path: Path, output_dir: Path) -> CleanStats:
    raw_text = input_path.read_text(encoding="utf-8", errors="replace")
    clean, start_found, end_found = clean_text(raw_text)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / input_path.name
    output_path.write_text(clean, encoding="utf-8")

    return CleanStats(
        source_file=str(input_path),
        output_file=str(output_path),
        raw_chars=len(raw_text),
        clean_chars=len(clean),
        raw_sha256=sha256_text(raw_text),
        clean_sha256=sha256_text(clean),
        estimated_words=estimate_word_count(clean),
        estimated_quote_count=estimate_quote_count(clean),
        gutenberg_start_found=start_found,
        gutenberg_end_found=end_found,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean raw Sherlock Holmes Project Gutenberg text files.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("./raw"),
        help="Directory containing raw .txt files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./clean"),
        help="Directory where cleaned .txt files will be written.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("./metadata/clean_manifest.json"),
        help="Path for the JSON cleaning manifest.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {args.input_dir}")

    input_files = list(iter_text_files(args.input_dir))
    if not input_files:
        raise FileNotFoundError(f"No .txt files found in: {args.input_dir}")

    stats: list[CleanStats] = []

    for input_path in input_files:
        file_stats = clean_file(input_path, args.output_dir)
        stats.append(file_stats)
        print(
            f"Cleaned {input_path.name}: "
            f"{file_stats.raw_chars:,} chars -> {file_stats.clean_chars:,} chars, "
            f"~{file_stats.estimated_words:,} words, "
            f"~{file_stats.estimated_quote_count:,} quote pairs"
        )

        if not file_stats.gutenberg_start_found:
            print(f"  WARNING: Gutenberg START marker not found in {input_path.name}")
        if not file_stats.gutenberg_end_found:
            print(f"  WARNING: Gutenberg END marker not found in {input_path.name}")

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps([asdict(item) for item in stats], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    total_words = sum(item.estimated_words for item in stats)
    total_quotes = sum(item.estimated_quote_count for item in stats)

    print("\nDone.")
    print(f"Files cleaned: {len(stats)}")
    print(f"Total estimated words: {total_words:,}")
    print(f"Total estimated quote pairs: {total_quotes:,}")
    print(f"Manifest written to: {args.manifest}")


if __name__ == "__main__":
    main()
