"""Offline integration gates, not evidence of Kogoro recognizability or fidelity."""

import hashlib
import json
from itertools import combinations
from pathlib import Path

import pytest

from multi_agent_personalities.application import run_conversation
from multi_agent_personalities.application.investigation_mock_runtime import (
    build_investigation_mock_runtime,
)
from multi_agent_personalities.character_catalog import load_character_catalog
from multi_agent_personalities.models import (
    ConversationRun, GenerationMetadata, GenerationResult, Message, Persona,
)
from multi_agent_personalities.persona_extraction.prompt import load_corpora


ROOT = Path(__file__).resolve().parents[1]
KOGORO = ROOT / "characters/kogoro"
METADATA = KOGORO / "metadata"
PERSONA = KOGORO / "kogoro_persona_curated_candidate.json"
SLUGS = ("sherlock", "poirot", "layton", "kogoro")
SELECTIONS = [group for size in (2, 3, 4) for group in combinations(SLUGS, size)]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_persona_schema_identity_synthetic_examples_and_import_integrity() -> None:
    persona = Persona.model_validate_json(PERSONA.read_text(encoding="utf-8"))
    assert len(persona.model_dump()) == 8
    assert (persona.character_id, persona.display_name) == ("kogoro_mouri", "Kogoro Mori")
    examples = read_json(METADATA / "example_message_provenance.json")
    provenance = read_json(METADATA / "entry_provenance.json")
    assert examples["all_examples_newly_written"] is True
    assert examples["all_canonical_quotations"] is False
    assert len(persona.example_messages) == len(examples["examples"]) == 6
    assert [entry["index"] for entry in examples["examples"]] == list(range(6))
    for entry in examples["examples"]:
        assert entry["kind"] == "synthetic_illustrative"
        assert entry["canonical_quote"] is False
        assert entry["underlying_evidence_ids"]
        assert set(entry["underlying_evidence_ids"]) <= provenance.keys()

    manifest = read_json(METADATA / "integration_manifest.json")
    original_hashes = {
        name: digest for digest, name in (
            line.split() for line in (METADATA / "research_SHA256SUMS").read_text().splitlines()
        )
    }
    for original, imported in manifest["imported_files"].items():
        digest = hashlib.sha256((KOGORO / imported).read_bytes()).hexdigest()
        assert digest == manifest["files_sha256"][imported]
        if original in original_hashes:
            assert digest == original_hashes[original]


def test_editorial_corpus_schema_and_complete_provenance() -> None:
    records = load_corpora(KOGORO / "corpus/persona_corpus.jsonl")
    provenance = read_json(METADATA / "entry_provenance.json")
    inventory = read_json(METADATA / "source_inventory.json")
    sources = {entry["source_id"]: entry for entry in inventory["source_entries"]}
    manifest = read_json(METADATA / "integration_manifest.json")
    assert len(records) == len(provenance) == 36
    assert {record["id"] for record in records} == set(provenance)
    assert [record["id"] for record in records] == manifest["included_ids"]
    assert len({record["text"].strip().casefold() for record in records}) == 36
    assert len({record["source"] for record in records}) == 21
    assert inventory["primary_manga_pages_directly_reviewed"] is False
    for record in records:
        assert set(record) == {
            "id", "character_id", "source", "text", "context", "traits", "confidence",
        }
        assert record["character_id"] == "kogoro_mouri"
        assert isinstance(record["text"], str) and record["text"].strip()
        assert isinstance(record["context"], str) and record["context"].strip()
        assert record["traits"] and all(isinstance(t, str) and t for t in record["traits"])
        assert 0.85 <= record["confidence"] <= 1
        entry = provenance[record["id"]]
        assert entry["derived_from_source_id"] == record["source"]
        assert entry["evidence_kind"] == "original_english_editorial_summary"
        assert entry["canonical_dialogue"] is False
        assert entry["direct_manga_panel_verified"] is False
        assert entry["text_originally_authored_for_project"] is True
        assert entry["speaker_attribution"] == "narrative_about_kogoro_not_character_speech"
        source = sources[record["source"]]
        assert source["urls"]
        assert source["verified_original_manga_dialogue"] is False
        assert source["has_direct_character_dialogue"] is False


def test_catalog_registers_fourth_character_with_separate_mock_reply() -> None:
    catalog = load_character_catalog(ROOT / "configs/characters.yaml")
    assert tuple(entry.slug for entry in catalog.characters) == SLUGS
    entry = catalog.characters[3]
    assert (entry.character_id, entry.display_name) == ("kogoro_mouri", "Kogoro Mori")
    assert entry.persona_fixture_path == PERSONA
    assert entry.corpus_path == KOGORO / "corpus/persona_corpus.jsonl"
    assert entry.mock_response_fixture_path == ROOT / "tests/fixtures/kogoro_agent_response.txt"
    reply = entry.mock_response_fixture_path.read_text().strip()
    persona = Persona.model_validate_json(PERSONA.read_text())
    assert reply and reply not in persona.example_messages
    assert reply not in [record["text"] for record in load_corpora(entry.corpus_path)]


@pytest.mark.parametrize("slugs", SELECTIONS)
def test_all_pairs_trios_and_four_agents_round_robin_and_persistence(tmp_path: Path, slugs) -> None:
    result = run_conversation(
        character_slugs=slugs, topic="How should we check a witness's timeline?",
        turn_count=2 * len(slugs), output_root=tmp_path, project_root=ROOT,
    )
    catalog = load_character_catalog(ROOT / "configs/characters.yaml")
    ids = {entry.slug: entry.character_id for entry in catalog.characters}
    assert tuple(result.run.character_ids) == tuple(ids[slug] for slug in slugs)
    assert [message.speaker_character_id for message in result.run.messages] == [
        ids[slug] for slug in slugs * 2
    ]
    assert {path.name for path in result.artifact_directory.iterdir()} == {
        "run.json", "messages.jsonl", "transcript.md",
    }
    assert ConversationRun.model_validate_json(
        (result.artifact_directory / "run.json").read_text()
    ) == result.run
    assert [Message.model_validate_json(line) for line in
            (result.artifact_directory / "messages.jsonl").read_text().splitlines()] == list(result.run.messages)
    transcript = result.transcript_path.read_text()
    for message in result.run.messages:
        assert message.speaker_name in transcript and message.text in transcript
        if message.speaker_character_id == "kogoro_mouri":
            assert message.text == (ROOT / "tests/fixtures/kogoro_agent_response.txt").read_text()


def test_copilot_prompt_uses_exact_curated_persona_offline(tmp_path: Path) -> None:
    prompts = []

    class OfflineProvider:
        def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
            assert task_name == "agent_reply"
            prompts.append(prompt)
            return GenerationResult(
                text="Synthetic offline provider response.",
                metadata=GenerationMetadata(provider="copilot"),
            )

    result = run_conversation(
        character_slugs=SLUGS, topic="Discuss an uncertain explanation.", turn_count=4,
        provider="copilot", output_root=tmp_path, project_root=ROOT,
        _copilot_provider_factory=lambda model: OfflineProvider(),
    )
    assert len(prompts) == 4
    persona = Persona.model_validate_json(PERSONA.read_text())
    system = prompts[3].split("## Conversation topic")[0]
    assert persona.display_name in system and persona.description in system
    for field in ("speaking_style", "reasoning_style", "personality_traits", "behavior_rules", "example_messages"):
        assert all(item in system for item in getattr(persona, field))
    assert result.run.messages[3].speaker_character_id == persona.character_id
    assert (ROOT / "tests/fixtures/kogoro_agent_response.txt").read_text().strip() not in prompts[3]


@pytest.mark.parametrize("slugs", [("sherlock", "kogoro"), SLUGS])
def test_kogoro_remains_unsupported_for_investigation(slugs) -> None:
    with pytest.raises(ValueError, match="unsupported by the current investigation"):
        build_investigation_mock_runtime(
            character_slugs=slugs, session_sequence=1, project_root=ROOT,
        )
