#!/usr/bin/env python3
"""Clean raw Project Gutenberg text files for the Hercule Poirot corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


START_MARKERS = (
    "*** START OF THE PROJECT GUTENBERG EBOOK",
    "*** START OF THIS PROJECT GUTENBERG EBOOK",
)

END_MARKERS = (
    "*** END OF THE PROJECT GUTENBERG EBOOK",
    "*** END OF THIS PROJECT GUTENBERG EBOOK",
)

UNICODE_REPLACEMENTS = {
    "\ufeff": "",
    "\u00a0": " ",
    "\u200b": "",
    "\r\n": "\n",
    "\r": "\n",
    "–": "-",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
}

DROP_LINE_PATTERNS = (
    re.compile(r"^\s*Produced by\b", re.IGNORECASE),
    re.compile(r"^\s*Transcribed from\b", re.IGNORECASE),
    re.compile(r"^\s*Updated editions will replace\b", re.IGNORECASE),
    re.compile(r"^\s*Creating the works from print editions\b", re.IGNORECASE),
    re.compile(r"^\s*This file was produced from images\b", re.IGNORECASE),
    re.compile(r"^\s*Character set encoding\b", re.IGNORECASE),
    re.compile(r"^\s*\[Illustration", re.IGNORECASE),
    re.compile(r"^\s*\[Footnote", re.IGNORECASE),
)

CHARACTER_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_INPUT_DIRECTORY = CHARACTER_DIRECTORY / "raw"
DEFAULT_OUTPUT_DIRECTORY = CHARACTER_DIRECTORY / "clean"
DEFAULT_MANIFEST_PATH = CHARACTER_DIRECTORY / "metadata" / "clean_manifest.json"


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
    """Remove the Gutenberg license header and footer from a text."""

    upper_text = text.upper()
    start_index = None

    for marker in START_MARKERS:
        marker_index = upper_text.find(marker)
        if marker_index != -1:
            newline_index = text.find("\n", marker_index)
            start_index = (
                newline_index + 1
                if newline_index != -1
                else marker_index + len(marker)
            )
            break

    end_index = None
    for marker in END_MARKERS:
        marker_index = upper_text.find(marker)
        if marker_index != -1:
            end_index = marker_index
            break

    start_found = start_index is not None
    end_found = end_index is not None
    body_start = start_index if start_index is not None else 0
    body_end = end_index if end_index is not None else len(text)

    if body_end < body_start:
        return text, start_found, end_found

    return text[body_start:body_end], start_found, end_found


def drop_noise_lines(text: str) -> str:
    cleaned_lines = []

    for line in text.split("\n"):
        stripped = line.strip()

        if any(pattern.search(stripped) for pattern in DROP_LINE_PATTERNS):
            continue
        if re.fullmatch(r"[\s*_\-=~]{3,}", stripped):
            continue

        cleaned_lines.append(line.rstrip())

    return "\n".join(cleaned_lines)


def fix_hyphenated_line_breaks(text: str) -> str:
    """Join lowercase words split by hard-wrapped, hyphenated line breaks."""

    return re.sub(r"([A-Za-z])-[ \t]*\n[ \t]*([a-z])", r"\1\2", text)


def rebuild_paragraphs(text: str) -> str:
    """Join hard-wrapped lines while preserving paragraph boundaries."""

    paragraphs = []
    current_lines = []

    for line in text.split("\n"):
        stripped = line.strip()

        if not stripped:
            if current_lines:
                paragraphs.append(" ".join(current_lines))
                current_lines = []
            continue

        current_lines.append(stripped)

    if current_lines:
        paragraphs.append(" ".join(current_lines))

    normalized = (
        re.sub(r"[ \t]{2,}", " ", paragraph).strip()
        for paragraph in paragraphs
    )
    return "\n\n".join(paragraph for paragraph in normalized if paragraph)


def final_cleanup(text: str) -> str:
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def estimate_word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def estimate_quote_count(text: str) -> int:
    return text.count('"') // 2


def clean_text(raw_text: str) -> tuple[str, bool, bool]:
    text = normalize_unicode(raw_text)
    text, start_found, end_found = strip_gutenberg_boilerplate(text)
    text = drop_noise_lines(text)
    text = fix_hyphenated_line_breaks(text)
    text = rebuild_paragraphs(text)
    text = final_cleanup(text)
    return text, start_found, end_found


def iter_text_files(input_directory: Path) -> Iterable[Path]:
    yield from sorted(input_directory.glob("*.txt"))


def clean_file(input_path: Path, output_directory: Path) -> CleanStats:
    raw_text = input_path.read_text(encoding="utf-8", errors="replace")
    clean, start_found, end_found = clean_text(raw_text)

    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / input_path.name
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
    parser = argparse.ArgumentParser(
        description="Clean raw Hercule Poirot Project Gutenberg text files."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIRECTORY,
        help="Directory containing raw .txt files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Directory where cleaned .txt files will be written.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path for the JSON cleaning manifest.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.input_dir.exists():
        raise FileNotFoundError(
            f"Input directory does not exist: {args.input_dir}"
        )

    input_files = list(iter_text_files(args.input_dir))
    if not input_files:
        raise FileNotFoundError(
            f"No .txt files found in: {args.input_dir}"
        )

    stats = []

    for input_path in input_files:
        file_stats = clean_file(input_path, args.output_dir)
        stats.append(file_stats)
        print(
            f"Cleaned {input_path.name}: "
            f"{file_stats.raw_chars:,} chars -> "
            f"{file_stats.clean_chars:,} chars, "
            f"~{file_stats.estimated_words:,} words, "
            f"~{file_stats.estimated_quote_count:,} quote pairs"
        )

        if not file_stats.gutenberg_start_found:
            print(
                "  WARNING: Gutenberg START marker not found in "
                f"{input_path.name}"
            )
        if not file_stats.gutenberg_end_found:
            print(
                "  WARNING: Gutenberg END marker not found in "
                f"{input_path.name}"
            )

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(
            [asdict(item) for item in stats],
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print("\nDone.")
    print(f"Files cleaned: {len(stats)}")
    print(
        "Total estimated words: "
        f"{sum(item.estimated_words for item in stats):,}"
    )
    print(
        "Total estimated quote pairs: "
        f"{sum(item.estimated_quote_count for item in stats):,}"
    )
    print(f"Manifest written to: {args.manifest}")


if __name__ == "__main__":
    main()
