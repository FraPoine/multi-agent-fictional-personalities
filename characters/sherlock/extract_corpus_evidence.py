#!/usr/bin/env python3
"""
Extract both Sherlock dialogue quotes and narrative evidence from clean plaintext files.

Repo location:
    characters/sherlock/extract_corpus_evidence.py

Input:
    characters/sherlock/clean/*.txt

Outputs:
    characters/sherlock/quotes/by_confidence/holmes_high_confidence.jsonl
    characters/sherlock/quotes/by_confidence/holmes_medium_confidence.jsonl
    characters/sherlock/quotes/by_confidence/holmes_low_confidence.jsonl
    characters/sherlock/quotes/by_confidence/not_holmes.jsonl
    characters/sherlock/quotes/by_confidence/unknown.jsonl

    characters/sherlock/evidence/holmes_descriptions_high_confidence.jsonl
    characters/sherlock/evidence/holmes_descriptions_medium_confidence.jsonl
    characters/sherlock/evidence/holmes_descriptions_low_confidence.jsonl

    characters/sherlock/metadata/corpus_evidence_manifest.json

Usage from characters/sherlock:
    python extract_corpus_evidence.py
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SPEECH_VERBS = [
    "said",
    "asked",
    "answered",
    "replied",
    "cried",
    "remarked",
    "observed",
    "continued",
    "returned",
    "murmured",
    "whispered",
    "exclaimed",
    "suggested",
    "added",
    "explained",
]

VERBS_PATTERN = r"(?:" + "|".join(SPEECH_VERBS) + r")"
HOLMES_PATTERN = r"(?:Mr\.?\s+)?(?:Sherlock\s+)?Holmes"

NON_HOLMES_PATTERN = r"""
    Watson|
    Lestrade|
    Gregson|
    Moriarty|
    Mycroft|
    Inspector|
    Mrs\.?|
    Miss|
    Lord|
    Sir|
    Dr\.?\s+Watson
"""

QUOTE_RE = re.compile(r'"([^"\n]{1,2000})"')

# Narrative evidence categories.
# These are intentionally simple, dependency-free heuristics.
EVIDENCE_KEYWORDS = {
    "appearance": [
        "face", "eyes", "features", "figure", "hands", "head", "voice",
        "tall", "thin", "pale", "gaunt", "sharp", "keen", "aquiline",
    ],
    "reasoning_method": [
        "deduction", "deduce", "deduced", "deductive", "inference", "inferred",
        "observe", "observed", "observation", "analysis", "reasoning", "method",
        "clue", "evidence", "conclusion", "logical",
    ],
    "temperament": [
        "cold", "calm", "eager", "impatient", "quiet", "silent", "restless",
        "excited", "languid", "energetic", "melancholy", "ironic", "detached",
    ],
    "habits": [
        "pipe", "tobacco", "violin", "chemical", "cocaine", "habit", "breakfast",
        "experiment", "laboratory", "monograph", "newspaper", "disguise",
    ],
    "social_behavior": [
        "smiled", "laughed", "shrugged", "bowed", "listened", "interrupted",
        "sprang", "leaned", "paced", "sat", "rose", "turned", "glanced",
    ],
}

HIGH_DESCRIPTION_PATTERNS = [
    rf"\b{HOLMES_PATTERN}\s+(?:was|is|had|has|seemed|appeared|looked|became|remained)\b",
    rf"\b{HOLMES_PATTERN}\s+(?:smiled|laughed|shrugged|sprang|leaned|paced|sat|rose|turned|glanced)\b",
    rf"\b{HOLMES_PATTERN}'s\s+(?:face|eyes|voice|manner|method|mind|habit|expression)\b",
    r"\bmy friend\s+(?:was|had|seemed|appeared|looked|became|remained)\b",
]

MEDIUM_DESCRIPTION_PATTERNS = [
    rf"\b{HOLMES_PATTERN}\b",
    r"\bmy friend\b",
    r"\bmy companion\b",
]


def sentence_split(text: str) -> list[tuple[int, int, str]]:
    """Tiny sentence splitter returning char spans and sentence text."""
    sentences: list[tuple[int, int, str]] = []
    start = 0

    for match in re.finditer(r"(?<=[.!?])\s+", text):
        end = match.start()
        sentence = text[start:end].strip()
        if sentence:
            sentences.append((start, end, sentence))
        start = match.end()

    tail = text[start:].strip()
    if tail:
        sentences.append((start, len(text), tail))

    return sentences


def classify_quote(before: str, after: str) -> dict[str, str]:
    before_window = before[-350:]
    after_window = after[:350]
    local_context = before_window + " " + after_window

    explicit_holmes_after = rf"\b{VERBS_PATTERN}\s+{HOLMES_PATTERN}\b"
    explicit_holmes_before = rf"\b{HOLMES_PATTERN}\s+{VERBS_PATTERN}\b"
    explicit_non_holmes_after = rf"\b{VERBS_PATTERN}\s+(?:{NON_HOLMES_PATTERN})\b"
    explicit_non_holmes_before = rf"\b(?:{NON_HOLMES_PATTERN})\s+{VERBS_PATTERN}\b"

    if re.search(explicit_holmes_after, after_window, flags=re.IGNORECASE | re.VERBOSE):
        return {"speaker": "sherlock_holmes", "confidence": "high", "rule": "explicit_holmes_after_quote"}

    if re.search(explicit_holmes_before, before_window, flags=re.IGNORECASE | re.VERBOSE):
        return {"speaker": "sherlock_holmes", "confidence": "high", "rule": "explicit_holmes_before_quote"}

    if re.search(explicit_non_holmes_after, after_window, flags=re.IGNORECASE | re.VERBOSE):
        return {"speaker": "not_holmes", "confidence": "high", "rule": "explicit_non_holmes_after_quote"}

    if re.search(explicit_non_holmes_before, before_window, flags=re.IGNORECASE | re.VERBOSE):
        return {"speaker": "not_holmes", "confidence": "high", "rule": "explicit_non_holmes_before_quote"}

    holmes_nearby = re.search(HOLMES_PATTERN, local_context, flags=re.IGNORECASE)
    medium_after_patterns = [
        rf"\b{VERBS_PATTERN}\s+my friend\b",
        rf"\b{VERBS_PATTERN}\s+my companion\b",
        rf"\b{VERBS_PATTERN}\s+he\b",
    ]

    if holmes_nearby:
        for pattern in medium_after_patterns:
            if re.search(pattern, after_window, flags=re.IGNORECASE):
                return {
                    "speaker": "sherlock_holmes",
                    "confidence": "medium",
                    "rule": "friend_or_pronoun_after_quote_with_holmes_nearby",
                }

        return {
            "speaker": "possible_sherlock_holmes",
            "confidence": "low",
            "rule": "holmes_nearby_no_clear_speech_verb",
        }

    return {"speaker": "unknown", "confidence": "none", "rule": "no_reliable_attribution"}


def quote_bucket(row: dict[str, Any]) -> str:
    prediction = row["speaker_prediction"]
    speaker = prediction["speaker"]
    confidence = prediction["confidence"]

    if speaker == "sherlock_holmes" and confidence == "high":
        return "holmes_high_confidence"
    if speaker == "sherlock_holmes" and confidence == "medium":
        return "holmes_medium_confidence"
    if speaker == "possible_sherlock_holmes":
        return "holmes_low_confidence"
    if speaker == "not_holmes":
        return "not_holmes"
    return "unknown"


def extract_quotes(text: str, source_file: Path, context_chars: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for idx, match in enumerate(QUOTE_RE.finditer(text), start=1):
        quote = match.group(1).strip()
        start = match.start()
        end = match.end()
        before = text[max(0, start - context_chars):start]
        after = text[end:min(len(text), end + context_chars)]

        rows.append(
            {
                "record_type": "quote",
                "quote_id": f"{source_file.stem}_quote_{idx:05d}",
                "source_file": str(source_file),
                "char_start": start,
                "char_end": end,
                "text": quote,
                "before_context": before,
                "after_context": after,
                "speaker_prediction": classify_quote(before=before, after=after),
            }
        )

    return rows


def categories_for_text(text: str) -> list[str]:
    lower = text.lower()
    categories = []

    for category, keywords in EVIDENCE_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            categories.append(category)

    return categories or ["general_character_evidence"]


def classify_description(sentence: str) -> dict[str, Any] | None:
    # Ignore direct dialogue lines; descriptions should be narrative evidence.
    if sentence.count('"') >= 2:
        return None

    for pattern in HIGH_DESCRIPTION_PATTERNS:
        if re.search(pattern, sentence, flags=re.IGNORECASE):
            return {
                "character": "sherlock_holmes",
                "confidence": "high",
                "rule": "explicit_holmes_description_pattern",
                "categories": categories_for_text(sentence),
            }

    for pattern in MEDIUM_DESCRIPTION_PATTERNS:
        if re.search(pattern, sentence, flags=re.IGNORECASE):
            categories = categories_for_text(sentence)
            confidence = "medium" if categories != ["general_character_evidence"] else "low"
            return {
                "character": "sherlock_holmes",
                "confidence": confidence,
                "rule": "holmes_mention_with_or_without_trait_keywords",
                "categories": categories,
            }

    return None


def evidence_bucket(row: dict[str, Any]) -> str:
    confidence = row["evidence_prediction"]["confidence"]
    if confidence == "high":
        return "holmes_descriptions_high_confidence"
    if confidence == "medium":
        return "holmes_descriptions_medium_confidence"
    return "holmes_descriptions_low_confidence"


def extract_descriptions(text: str, source_file: Path, context_chars: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for idx, (start, end, sentence) in enumerate(sentence_split(text), start=1):
        prediction = classify_description(sentence)
        if prediction is None:
            continue

        before = text[max(0, start - context_chars):start]
        after = text[end:min(len(text), end + context_chars)]

        rows.append(
            {
                "record_type": "description",
                "evidence_id": f"{source_file.stem}_evidence_{idx:05d}",
                "source_file": str(source_file),
                "char_start": start,
                "char_end": end,
                "text": sentence,
                "before_context": before,
                "after_context": after,
                "evidence_prediction": prediction,
            }
        )

    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("./clean"))
    parser.add_argument("--quote-output-dir", type=Path, default=Path("./quotes/by_confidence"))
    parser.add_argument("--evidence-output-dir", type=Path, default=Path("./evidence"))
    parser.add_argument("--manifest", type=Path, default=Path("./metadata/corpus_evidence_manifest.json"))
    parser.add_argument("--context-chars", type=int, default=500)
    args = parser.parse_args()

    clean_files = sorted(args.input_dir.glob("*.txt"))
    if not clean_files:
        raise FileNotFoundError(f"No .txt files found in {args.input_dir}")

    quote_buckets: dict[str, list[dict[str, Any]]] = {
        "holmes_high_confidence": [],
        "holmes_medium_confidence": [],
        "holmes_low_confidence": [],
        "not_holmes": [],
        "unknown": [],
    }

    evidence_buckets: dict[str, list[dict[str, Any]]] = {
        "holmes_descriptions_high_confidence": [],
        "holmes_descriptions_medium_confidence": [],
        "holmes_descriptions_low_confidence": [],
    }

    quote_rule_counts = Counter()
    evidence_rule_counts = Counter()
    evidence_category_counts = Counter()
    file_counts: dict[str, dict[str, int]] = {}

    for path in clean_files:
        text = path.read_text(encoding="utf-8")

        quote_rows = extract_quotes(text=text, source_file=path, context_chars=args.context_chars)
        evidence_rows = extract_descriptions(text=text, source_file=path, context_chars=args.context_chars)

        file_counts[path.name] = {
            "quotes": len(quote_rows),
            "descriptions": len(evidence_rows),
        }

        for row in quote_rows:
            bucket = quote_bucket(row)
            quote_buckets[bucket].append(row)
            quote_rule_counts[row["speaker_prediction"]["rule"]] += 1

        for row in evidence_rows:
            bucket = evidence_bucket(row)
            evidence_buckets[bucket].append(row)
            pred = row["evidence_prediction"]
            evidence_rule_counts[pred["rule"]] += 1
            for category in pred["categories"]:
                evidence_category_counts[category] += 1

    for name, rows in quote_buckets.items():
        write_jsonl(args.quote_output_dir / f"{name}.jsonl", rows)

    for name, rows in evidence_buckets.items():
        write_jsonl(args.evidence_output_dir / f"{name}.jsonl", rows)

    manifest = {
        "input_dir": str(args.input_dir),
        "quote_output_dir": str(args.quote_output_dir),
        "evidence_output_dir": str(args.evidence_output_dir),
        "context_chars": args.context_chars,
        "total_quotes": sum(len(rows) for rows in quote_buckets.values()),
        "total_descriptions": sum(len(rows) for rows in evidence_buckets.values()),
        "quote_counts": {name: len(rows) for name, rows in quote_buckets.items()},
        "evidence_counts": {name: len(rows) for name, rows in evidence_buckets.items()},
        "evidence_category_counts": dict(evidence_category_counts),
        "quote_rule_counts": dict(quote_rule_counts),
        "evidence_rule_counts": dict(evidence_rule_counts),
        "file_counts": file_counts,
    }

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Done.")
    print("Quote counts:")
    print(json.dumps(manifest["quote_counts"], indent=2, ensure_ascii=False))
    print("Description counts:")
    print(json.dumps(manifest["evidence_counts"], indent=2, ensure_ascii=False))
    print(f"Manifest written to: {args.manifest}")


if __name__ == "__main__":
    main()
