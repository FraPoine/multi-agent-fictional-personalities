"""Offline gates for the curated Layton conversation candidate and its provenance."""

import hashlib
import json
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
LAYTON = ROOT / "characters/layton"
METADATA = LAYTON / "metadata"
PERSONA = LAYTON / "layton_persona_curated_candidate.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_curated_persona_identity_examples_and_research_hashes() -> None:
    persona = Persona.model_validate_json(PERSONA.read_text(encoding="utf-8"))
    assert len(persona.model_dump()) == 8
    assert persona.character_id == "professor_layton"
    assert persona.display_name == "Professor Layton"
    examples = read_json(METADATA / "example_message_provenance.json")
    assert [entry["index"] for entry in examples["example_messages"]] == list(
        range(len(persona.example_messages))
    )
    assert len(persona.example_messages) == 6
    assert all(
        entry["kind"] == "newly_written_illustrative"
        and entry["canonical_quote"] is False
        for entry in examples["example_messages"]
    )
    research_hashes = dict(
        (name, digest)
        for digest, name in (
            line.split() for line in
            (METADATA / "research_SHA256SUMS").read_text().splitlines()
        )
    )
    # These imported sidecars and the renamed Persona are byte-for-byte originals.
    for name in (
        "source_inventory.json", "entry_provenance.json",
        "example_message_provenance.json", "methodology_and_qa.md",
    ):
        assert hashlib.sha256((METADATA / name).read_bytes()).hexdigest() == (
            research_hashes[name]
        )
    assert hashlib.sha256(PERSONA.read_bytes()).hexdigest() == research_hashes[
        "professor_layton_persona_draft.json"
    ]
    manifest = read_json(METADATA / "integration_manifest.json")
    for name, digest in manifest["files_sha256"].items():
        assert hashlib.sha256((LAYTON / name).read_bytes()).hexdigest() == digest


def test_summary_corpus_contract_and_excluded_quote_provenance() -> None:
    records = load_corpora(LAYTON / "corpus/persona_corpus.jsonl")
    provenance = read_json(METADATA / "entry_provenance.json")
    sources = {
        item["source_id"]: item
        for item in read_json(METADATA / "source_inventory.json")["source_entries"]
    }
    manifest = read_json(METADATA / "integration_manifest.json")
    assert len(records) == 35
    assert len({record["id"] for record in records}) == 35
    assert len({record["text"].strip().casefold() for record in records}) == 35
    assert [record["id"] for record in records] == manifest["included_ids"]
    assert len(manifest["excluded_ids"]) == 13
    assert set(provenance) == set(manifest["included_ids"] + manifest["excluded_ids"])
    assert set(manifest["included_ids"]).isdisjoint(manifest["excluded_ids"])
    for record in records:
        assert set(record) == {
            "id", "character_id", "source", "text", "context", "traits", "confidence",
        }
        assert record["character_id"] == "professor_layton"
        assert isinstance(record["text"], str) and record["text"].strip()
        assert 0.85 <= record["confidence"] <= 1
        assert record["traits"] and all(isinstance(t, str) and t for t in record["traits"])
        assert "NOT a quotation" in record["context"]
        entry = provenance[record["id"]]
        assert entry["evidence_kind"] == "editorial_paraphrase"
        assert entry["source_id"] == record["source"]
    for entry_id, entry in provenance.items():
        source = sources[entry["source_id"]]
        assert source["url"] == entry["transcript_url"]
        assert source["firsthand_game_text_verified"] is False
        assert entry["primary_game_verification"] == "not_completed"
        if entry_id in manifest["excluded_ids"]:
            assert entry["evidence_kind"] == "short_quote_from_unofficial_fan_transcript"


def test_catalog_loads_curated_candidate_directly() -> None:
    entry = load_character_catalog(ROOT / "configs/characters.yaml").characters[2]
    assert entry.slug == "layton"
    assert entry.persona_fixture_path == PERSONA
    assert entry.corpus_path == LAYTON / "corpus/persona_corpus.jsonl"
    assert entry.mock_response_fixture_path == ROOT / "tests/fixtures/layton_agent_response.txt"


@pytest.mark.parametrize("slugs", [["sherlock", "poirot", "layton"], ["sherlock", "poirot"]])
def test_mock_round_robin_and_all_persisted_artifacts(tmp_path: Path, slugs) -> None:
    result = run_conversation(
        character_slugs=slugs, topic="How should we test an uncertain explanation?",
        turn_count=6, output_root=tmp_path, project_root=ROOT,
        run_id="layton_regression",
    )
    ids = ["sherlock_holmes", "hercule_poirot", "professor_layton"][:len(slugs)]
    assert [m.speaker_character_id for m in result.run.messages] == [
        ids[i % len(ids)] for i in range(6)
    ]
    persisted = ConversationRun.model_validate_json(
        (result.artifact_directory / "run.json").read_text()
    )
    assert persisted == result.run
    assert [Message.model_validate_json(line) for line in
            (result.artifact_directory / "messages.jsonl").read_text().splitlines()] == list(result.run.messages)
    transcript = result.transcript_path.read_text()
    for message in result.run.messages:
        assert message.speaker_name in transcript and message.text in transcript
        if message.speaker_character_id == "professor_layton":
            assert message.text == (ROOT / "tests/fixtures/layton_agent_response.txt").read_text()


def test_copilot_route_receives_curated_persona_without_network(tmp_path: Path) -> None:
    prompts = []

    class OfflineProvider:
        def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
            assert task_name == "agent_reply"
            prompts.append(prompt)
            return GenerationResult(
                text="An original offline test response.",
                metadata=GenerationMetadata(provider="copilot"),
            )

    result = run_conversation(
        character_slugs=["sherlock", "poirot", "layton"],
        topic="Discuss the limits of an uncertain explanation.", turn_count=3,
        provider="copilot", output_root=tmp_path, project_root=ROOT,
        _copilot_provider_factory=lambda model: OfflineProvider(),
    )
    persona = Persona.model_validate_json(PERSONA.read_text())
    layton_prompt = prompts[2].split("## Conversation topic")[0]
    assert persona.description in layton_prompt
    for field in ("speaking_style", "reasoning_style", "personality_traits", "behavior_rules", "example_messages"):
        assert all(item in layton_prompt for item in getattr(persona, field))
    assert result.run.messages[2].speaker_character_id == persona.character_id
    assert (ROOT / "tests/fixtures/layton_agent_response.txt").read_text().strip() not in prompts[2]


def test_layton_remains_unsupported_for_investigation() -> None:
    with pytest.raises(ValueError, match="unsupported by the current investigation"):
        build_investigation_mock_runtime(
            character_slugs=["sherlock", "poirot", "layton"],
            session_sequence=1, project_root=ROOT,
        )
