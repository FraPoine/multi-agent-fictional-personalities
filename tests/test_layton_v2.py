"""Structural/data-integrity gates; these do not authenticate game dialogue."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import pytest
import yaml

from multi_agent_personalities.application import run_conversation
from multi_agent_personalities.application.conversation_service import _load_mock_participants
from multi_agent_personalities.character_catalog import load_character_catalog
from multi_agent_personalities.models import ConversationRun, Message, Persona
from multi_agent_personalities.persona_extraction.prompt import load_corpora, select_examples
from tests.test_live_conversation_service import RecordingProvider

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'characters/layton'
META = BASE / 'metadata'
CORPUS = BASE / 'corpus/persona_corpus_v2.jsonl'
V2 = BASE / 'layton_persona_curated_v2.json'
V1 = BASE / 'layton_persona_curated_candidate.json'
TRAITS = {
    'speaking_style', 'reasoning_style', 'social_behavior', 'curiosity',
    'humility', 'pedagogy', 'interaction_with_luke', 'politeness',
    'emotional_restraint', 'emotional_expression', 'observation', 'uncertainty',
    'empathy', 'moral_courage', 'humor', 'decisiveness',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def test_v2_corpus_schema_provenance_and_loader_compatibility() -> None:
    rows = [json.loads(line) for line in CORPUS.read_text().splitlines()]
    provenance = read(META / 'entry_provenance_v2.json')
    inventory = read(META / 'source_inventory_v2.json')
    sources = {s['source_id']: s for s in inventory['source_entries']}
    assert len(sources) == len(inventory['source_entries'])
    assert set(provenance) == {r['id'] for r in rows}
    assert len(rows) == len(provenance)
    assert len({' '.join(r['text'].casefold().split()) for r in rows}) == len(rows)
    assert set(inventory['trait_vocabulary']) == TRAITS
    assert load_corpora(CORPUS) == rows
    assert select_examples(rows) == select_examples(load_corpora(CORPUS))
    assert {r['id'] for r in select_examples(rows)} <= set(provenance)
    anchors = []
    for r in rows:
        assert set(r) == {'id','character_id','source','text','context','traits','confidence'}
        assert re.fullmatch(r'layton_v2_\d{4}', r['id'])
        assert r['character_id'] == 'professor_layton'
        assert r['text'].strip() and r['context'].strip()
        assert 'NOT a quotation' in r['context']
        assert isinstance(r['confidence'], float) and 0 <= r['confidence'] <= 1
        assert r['traits'] and set(r['traits']) <= TRAITS
        assert len(r['traits']) == len(set(r['traits']))
        source = sources[r['source']]
        p = provenance[r['id']]
        assert p['evidence_id'] == r['id']
        assert p['source_id'] == r['source']
        assert p['source_url'] == source['url']
        assert p['game'] == source['game']
        assert p['chapter'] == source['chapter']
        assert p['scene_anchor'] in source['inspected_scene_anchors']
        assert p['speaker_attribution_basis'].startswith('LAYTON-labelled')
        assert p['primary_game_verification'] == 'not_completed'
        assert p['verification_status'] == 'transcript_scene_inspected_primary_game_unverified'
        assert p['evidence_type'] == 'original_analytical_paraphrase'
        assert p['behavioral_dimensions']
        assert set(p['behavioral_dimensions']) <= set(inventory['dimension_vocabulary'])
        assert p['inspected_on'] == source['inspected_on']
        assert source['firsthand_game_text_verified'] is False
        assert source['source_type'] == 'unofficial_game_transcript'
        assert source['localization'] == 'US English (site index attribution)'
        assert source['accessibility'] == 'public_rendered_text_accessible'
        anchors.append((p['source_id'], p['scene_anchor']))
    assert len(anchors) == len(set(anchors))
    assert set(inventory['excluded_source_ids']).isdisjoint(sources)
    assert set(sources) == {r['source'] for r in rows}


def test_v2_persona_and_complete_evidence_mapping() -> None:
    persona = Persona.model_validate_json(V2.read_text())
    assert len(persona.model_dump()) == 8
    assert (persona.character_id, persona.display_name) == ('professor_layton', 'Professor Layton')
    assert persona != Persona.model_validate_json(V1.read_text())
    evidence = read(META / 'entry_provenance_v2.json')
    mapping = read(META / 'persona_v2_evidence_map.json')
    assert mapping['llm_extraction_performed'] is False
    assert mapping['scientific_validation'] is False
    expected_pointers = {('description', None)}
    for field in ('speaking_style','reasoning_style','personality_traits','behavior_rules','example_messages'):
        values = getattr(persona, field)
        assert values and all(v.strip() for v in values)
        expected_pointers.update((field, i) for i in range(len(values)))
    entries = mapping['elements']
    assert {(p['field'], p['index']) for p in entries} == expected_pointers
    assert len(entries) == len(expected_pointers)
    for p in entries:
        value = getattr(persona, p['field'])
        if p['index'] is not None:
            value = value[p['index']]
        assert hashlib.sha256(value.encode()).hexdigest() == p['value_sha256']
        assert p['supporting_evidence_ids']
        assert set(p['supporting_evidence_ids']) <= set(evidence)
        assert p['interpretation_note'].strip()
        if p['field'] == 'example_messages':
            assert p['support_type'] == 'newly_written_illustrative'
            assert p['canonical_quote'] is False


def test_historical_assets_v2_checksums_and_coverage_totals() -> None:
    manifest = read(META / 'integration_manifest_v2.json')
    # A new manifest supplements the original; it does not rewrite old assertions.
    for path, digest in manifest['historical_files_sha256'].items():
        assert hashlib.sha256((BASE / path).read_bytes()).hexdigest() == digest
    assert {'metadata/research_SHA256SUMS', 'metadata/integration_manifest.json',
            'corpus/persona_corpus.jsonl', 'layton_persona_curated_candidate.json'} <= set(manifest['historical_files_sha256'])
    for path, digest in manifest['files_sha256'].items():
        assert hashlib.sha256((BASE / path).read_bytes()).hexdigest() == digest
    for line in (META / 'v2_SHA256SUMS').read_text().splitlines():
        digest, path = line.split('  ', 1)
        assert hashlib.sha256((BASE / path).read_bytes()).hexdigest() == digest
    rows = load_corpora(CORPUS)
    p = read(META / 'entry_provenance_v2.json')
    assert manifest['record_count'] == len(rows)
    assert manifest['original_record_count'] == len(load_corpora(BASE / 'corpus/persona_corpus.jsonl'))
    assert manifest['counts_by_source'] == dict(Counter(r['source'] for r in rows))
    assert manifest['counts_by_game'] == dict(Counter(x['game'] for x in p.values()))
    assert manifest['counts_by_dimension'] == dict(Counter(d for x in p.values() for d in x['behavioral_dimensions']))
    assert manifest['optional_quit_record_count'] == sum(x['branch_type'] == 'optional_quit_response' for x in p.values())
    assert set(manifest['excluded_historical_quote_ids']).isdisjoint(p)
    assert manifest['quality_gate']['status'] == 'passed_for_live_candidate'
    assert manifest['quality_gate']['primary_game_authentication'] is False


def test_only_layton_live_configuration_changes() -> None:
    config = yaml.safe_load((ROOT / 'configs/characters.yaml').read_text())['characters']
    manifest = read(META / 'integration_manifest_v2.json')
    assert [x for x in config if x['slug'] != 'layton'] == manifest['preserved_character_configurations']
    layton = next(x for x in config if x['slug'] == 'layton')
    original = manifest['original_layton_configuration']
    assert {k:v for k,v in layton.items() if k != 'live_persona_path'} == {k:v for k,v in original.items() if k != 'live_persona_path'}
    assert layton['live_persona_path'] == manifest['live_persona_path']
    entry = load_character_catalog(ROOT / 'configs/characters.yaml').characters[2]
    assert entry.live_persona_path == V2
    assert entry.persona_fixture_path == V1
    assert _load_mock_participants(['layton','sherlock'], ROOT)[0].persona == Persona.model_validate_json(V1.read_text())


@pytest.mark.parametrize('variant', ['baseline_v1', 'dialogue_v2'])
def test_live_v2_prompt_calls_history_and_persistence(tmp_path: Path, variant: str) -> None:
    calls = []
    result = run_conversation(
        character_slugs=['layton','sherlock'], topic='How should we test an uncertain claim?',
        turn_count=4, provider='copilot', prompt_variant=variant,
        project_root=ROOT, output_root=tmp_path,
        _copilot_provider_factory=lambda model: RecordingProvider(model=model, calls=calls),
    )
    persona = Persona.model_validate_json(V2.read_text())
    assert len(calls) == 4
    assert [m.speaker_character_id for m in result.run.messages] == ['professor_layton','sherlock_holmes'] * 2
    for i in (0,2):
        profile = calls[i][2].split('## Conversation topic')[0]
        assert persona.description in profile
        for field in ('speaking_style','reasoning_style','personality_traits','behavior_rules','example_messages'):
            assert all(value in profile for value in getattr(persona, field))
    for i, (_, task, prompt) in enumerate(calls):
        assert task == 'agent_reply'
        for previous in result.run.messages[:i]:
            assert f'[Turn {previous.turn_index}] {previous.speaker_name}: {previous.text}' in prompt
    assert result.run.prompt_variant == variant
    assert ConversationRun.model_validate_json((result.artifact_directory / 'run.json').read_text()) == result.run
    assert [Message.model_validate_json(line) for line in (result.artifact_directory / 'messages.jsonl').read_text().splitlines()] == list(result.run.messages)
    for message in result.run.messages:
        assert message.generation_metadata.provider == 'copilot'
        assert message.text in result.transcript_path.read_text()
