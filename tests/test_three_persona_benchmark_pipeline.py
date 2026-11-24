import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from multi_agent_personalities.artifacts import save_conversation_run
from multi_agent_personalities.evaluation.benchmark import IDS, prepare_three_persona_benchmark
from multi_agent_personalities.evaluation.config import load_three_persona_benchmark_config
from multi_agent_personalities.models import ConversationRun, Message
from multi_agent_personalities.models.conversation import PersonaSource

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'configs/benchmark_three_personas_v1.yaml'
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def sources(tmp_path):
    config = load_three_persona_benchmark_config(CONFIG)
    runs = []
    mapping = {}
    for scenario in config.scenarios:
        run_id = 'source_' + scenario.id
        mapping[scenario.id] = run_id
        order = tuple(IDS[slug] for slug in scenario.speaker_order)
        messages = tuple(Message(message_id=f'{run_id}_msg_{i}', run_id=run_id, turn_index=i,
            speaker_character_id=order[i % 3], speaker_name='participant',
            text=f'Evidence for {scenario.id}, contribution {i}: uncertainty deserves careful thought.',
            provider='copilot', model=config.model, timestamp=NOW) for i in range(6))
        provenance = tuple(PersonaSource(character_id=IDS[slug], **config.personas[slug].model_dump()) for slug in scenario.speaker_order)
        run = ConversationRun(run_id=run_id, topic=scenario.topic, character_ids=order,
            turn_count=6, seed=42, provider='copilot', model=config.model, configured_model=config.model,
            status='completed', created_at=NOW, prompt_variant=config.prompt_variant,
            prompt_template_sha256=config.prompt_template_sha256, persona_sources=provenance, messages=messages)
        save_conversation_run(output_root=tmp_path, run=run)
        runs.append(run)
    manifest = tmp_path / 'sources.yaml'
    manifest.write_text(yaml.safe_dump({'sources': mapping}))
    return tmp_path, manifest, runs


def replace_run(root, run):
    directory = root / 'conversations' / 'runs' / run.run_id
    (directory / 'run.json').write_text(run.model_dump_json())
    (directory / 'messages.jsonl').write_text(''.join(m.model_dump_json() + '\n' for m in run.messages))


def prepare(source):
    root, manifest, _ = source
    return prepare_three_persona_benchmark(source_manifest=manifest, output_root=root, config_path=CONFIG)


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_balanced_deterministic_private_records(sources, tmp_path):
    target = prepare(sources)
    public = read_jsonl(target / 'trials_public.jsonl')
    answers = read_jsonl(target / 'answer_key.jsonl')
    assert len(public) == len(answers) == 18
    assert all(set(row) == {'trial_id', 'display_text', 'candidate_character_ids'} for row in public)
    assert all(row['turn_index'] >= 3 for row in answers)
    assert {x['trial_id'] for x in public} == {x['trial_id'] for x in answers}
    assert all(sum(x['correct_character_id'] == c for x in answers) == 6 for c in IDS.values())
    import shutil
    shutil.rmtree(target)
    again = prepare(sources)
    assert public == read_jsonl(again / 'trials_public.jsonl')
    assert answers == read_jsonl(again / 'answer_key.jsonl')


@pytest.mark.parametrize('change', ['old', 'model', 'prompt', 'topic', 'order', 'messages'])
def test_reject_bad_source(sources, change):
    root, _, runs = sources
    run = runs[0]
    if change == 'old':
        run = run.model_copy(update={'persona_sources': None})
    elif change == 'model':
        run = run.model_copy(update={'configured_model': None})
    elif change == 'prompt':
        run = run.model_copy(update={'prompt_template_sha256': '0' * 64})
    elif change == 'topic':
        run = run.model_copy(update={'topic': 'wrong topic'})
    elif change == 'order':
        messages = list(run.messages)
        messages[0] = messages[0].model_copy(update={'speaker_character_id': run.character_ids[1]})
        run = run.model_copy(update={'messages': tuple(messages)})
    else:
        run = run.model_copy(update={'status': 'running', 'messages': run.messages[:-1]})
    replace_run(root, run)
    with pytest.raises(ValueError):
        prepare(sources)
    assert not (root / 'evaluation' / 'benchmarks' / 'three_personas_v1').exists()


def test_mask_and_fallback(sources):
    root, _, runs = sources
    run = runs[0]
    messages = list(run.messages)
    messages[3] = messages[3].model_copy(update={'text': 'I am Sherlock Holmes.'})
    messages[0] = messages[0].model_copy(update={'text': 'Poirot, consider the conflicting evidence.'})
    replace_run(root, run.model_copy(update={'messages': tuple(messages)}))
    target = prepare(sources)
    answers = read_jsonl(target / 'answer_key.jsonl')
    selected = next(a for a in answers if a['source_run_id'] == run.run_id and a['correct_character_id'] == IDS['sherlock'])
    assert selected['turn_index'] == 0 and selected['mask_count'] == 1
    trial = next(t for t in read_jsonl(target / 'trials_public.jsonl') if t['trial_id'] == selected['trial_id'])
    assert trial['display_text'].startswith('[name]')
    review = json.loads((target / 'leakage_review.json').read_text())
    assert any(d.get('reason') == 'self_identification' for d in review['decisions'])


def test_duplicate_sources_rejected(sources):
    _, manifest, _ = sources
    data = yaml.safe_load(manifest.read_text())
    data['sources']['scenario_02'] = data['sources']['scenario_01']
    manifest.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match='distinct'):
        prepare(sources)


def test_live_generation_records_loaded_persona_bytes(tmp_path):
    import hashlib
    from multi_agent_personalities.application import run_conversation
    from multi_agent_personalities.models import GenerationMetadata, GenerationResult

    class OfflineProvider:
        def generate(self, prompt, *, task_name):
            return GenerationResult(text='A carefully considered response.', metadata=GenerationMetadata(provider='copilot', model='test-model'))

    result = run_conversation(character_slugs=['sherlock', 'poirot', 'layton'],
        topic='A neutral scenario', turn_count=6, provider='copilot', copilot_model='test-model',
        prompt_variant='dialogue_v2', output_root=tmp_path, project_root=ROOT,
        run_id='provenance_test', _copilot_provider_factory=lambda model: OfflineProvider())
    config = load_three_persona_benchmark_config(CONFIG)
    assert result.run.configured_model == 'test-model'
    assert result.run.prompt_template_sha256 == config.prompt_template_sha256
    for slug, source in zip(config.characters, result.run.persona_sources):
        assert source.path == config.personas[slug].path
        assert source.sha256 == hashlib.sha256((ROOT / source.path).read_bytes()).hexdigest()
    saved = ConversationRun.model_validate_json((result.artifact_directory / 'run.json').read_text())
    assert saved.persona_sources == result.run.persona_sources


def test_legacy_run_remains_readable(sources):
    run = sources[2][0]
    legacy = run.model_dump(exclude={'persona_sources', 'configured_model'})
    loaded = ConversationRun.model_validate(legacy)
    assert loaded.persona_sources is None and loaded.configured_model is None


def test_no_eligible_fallback_fails(sources):
    root, _, runs = sources
    run = runs[0]
    messages = list(run.messages)
    for i in (0, 3):
        messages[i] = messages[i].model_copy(update={'text': 'I am Sherlock Holmes.'})
    replace_run(root, run.model_copy(update={'messages': tuple(messages)}))
    with pytest.raises(ValueError, match='no eligible message'):
        prepare(sources)


def test_duplicate_selection_uses_first_contribution(sources):
    root, _, runs = sources
    first, second = runs[0], runs[1]
    messages = list(second.messages)
    messages[3] = messages[3].model_copy(update={'text': first.messages[3].text})
    replace_run(root, second.model_copy(update={'messages': tuple(messages)}))
    target = prepare(sources)
    selected = next(a for a in read_jsonl(target / 'answer_key.jsonl') if a['source_message_id'] == messages[0].message_id)
    assert selected['turn_index'] == 0
    review = json.loads((target / 'leakage_review.json').read_text())
    assert any(d.get('reason') == 'duplicate_text' for d in review['decisions'])


def test_missing_run_and_inconsistent_message_file_rejected(sources):
    root, _, runs = sources
    path = root / 'conversations' / 'runs' / runs[0].run_id / 'messages.jsonl'
    path.write_text('')
    with pytest.raises(ValueError, match='inconsistent'):
        prepare(sources)
    path.unlink()
    with pytest.raises(ValueError, match='invalid source run'):
        prepare(sources)


def test_complete_offline_human_workflow_and_review_gate(sources):
    import asyncio
    import httpx2
    from multi_agent_personalities.evaluation.benchmark_human import approve_review, analyze_benchmark, rater_order, load_public
    from multi_agent_personalities.web.rater_app import create_three_persona_rater_app

    target = prepare(sources)
    with pytest.raises(ValueError):
        create_three_persona_rater_app(benchmark_directory=target)
    approve_review(target, 'reviewer_test')
    app = create_three_persona_rater_app(benchmark_directory=target)
    class Client:
        def request(self, method, url, **kwargs):
            async def call():
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url='http://testserver', follow_redirects=True) as client:
                    return await client.request(method, url, **kwargs)
            return asyncio.run(call())
        def get(self, url, **kwargs):
            return self.request('GET', url, **kwargs)
        def post(self, url, **kwargs):
            return self.request('POST', url, **kwargs)
    client = Client()
    assert client.get('/answer_key.jsonl').status_code == 404
    assert client.get('/?rater_id=test_rater').text.count('Character familiarity') == 1
    assert client.post('/familiarity', data={'rater_id': 'test_rater', 'sherlock_holmes': '4', 'hercule_poirot': '2', 'professor_layton': '2'}).status_code == 400
    form = {'rater_id': 'test_rater', 'sherlock_holmes': '2', 'hercule_poirot': '2', 'professor_layton': '3'}
    assert client.post('/familiarity', data=form).status_code == 200
    assert client.post('/familiarity', data=form).status_code == 400
    trials = load_public(target)
    ordered, candidates = rater_order(trials, 42, 'test_rater')
    assert (ordered, candidates) == rater_order(trials, 42, 'test_rater')
    assert [x.trial_id for x in ordered] != [x.trial_id for x in rater_order(trials, 42, 'another_rater')[0]]
    premature = {'rater_id': 'test_rater', 'trial_id': ordered[1].trial_id, 'selected_character_id': 'sherlock_holmes', 'confidence': '4'}
    assert client.post('/responses', data=premature).status_code == 400
    assert not (target / 'responses.jsonl').exists()
    page = client.get('/?rater_id=test_rater').text
    assert all(name in page for name in ('Sherlock Holmes', 'Hercule Poirot', 'Professor Layton'))
    assert 'correct_character_id' not in page and 'source_message_id' not in page
    answers = {x['trial_id']: x['correct_character_id'] for x in read_jsonl(target / 'answer_key.jsonl')}
    for trial in ordered:
        submitted = {'rater_id': 'test_rater', 'trial_id': trial.trial_id, 'selected_character_id': answers[trial.trial_id], 'confidence': '4'}
        assert client.post('/responses', data=submitted).status_code == 200
    assert '18 responses' in client.get('/?rater_id=test_rater').text
    assert client.post('/responses', data=submitted).status_code == 400
    analysis = analyze_benchmark(target)
    assert analysis['primary_familiar_complete']['accuracy'] == 1
    assert analysis['all_responses']['correct'] == 18
    assert analysis['chance_baseline'] == 1 / 3
    assert analysis['agreement']['pairwise_percentage'] is None
    assert 'independent' in (target / 'report.md').read_text()
    assert client.get('/answer_key.jsonl').status_code == 404
    with (target / 'trials_public.jsonl').open('a') as handle:
        handle.write(' ')
    assert client.get('/?rater_id=test_rater').status_code == 503
    with pytest.raises(ValueError):
        create_three_persona_rater_app(benchmark_directory=target)


def test_empty_and_incomplete_analysis(sources):
    from multi_agent_personalities.evaluation.benchmark_human import approve_review, analyze_benchmark, submit_familiarity, submit_response
    target = prepare(sources)
    approve_review(target, 'reviewer_test')
    empty = analyze_benchmark(target)
    assert empty['primary_familiar_complete']['accuracy'] is None
    assert empty['all_responses']['accuracy'] is None
    submit_familiarity(target, 'rater_one', {'sherlock_holmes': 2, 'hercule_poirot': 2, 'professor_layton': 1})
    from multi_agent_personalities.evaluation.benchmark_human import load_public, rater_order
    trial = rater_order(load_public(target), 42, 'rater_one')[0][0]
    submit_response(target, 'rater_one', trial.trial_id, 'sherlock_holmes', 3)
    analysis = analyze_benchmark(target)
    assert analysis['incomplete_raters'] == 1
    assert analysis['primary_familiar_complete']['accuracy'] is None
    assert analysis['all_responses']['responses'] == 1


def test_analysis_familiarity_filter_confusion_and_agreement(sources):
    from multi_agent_personalities.evaluation.benchmark_human import approve_review, analyze_benchmark, submit_familiarity, submit_response
    target = prepare(sources)
    approve_review(target, 'reviewer_test')
    submit_familiarity(target, 'eligible_rater', dict.fromkeys(IDS.values(), 2))
    submit_familiarity(target, 'unfamiliar_rater', dict.fromkeys(IDS.values(), 1))
    answers = read_jsonl(target / 'answer_key.jsonl')
    from multi_agent_personalities.evaluation.benchmark_human import load_public, rater_order
    by_id = {a['trial_id']: a for a in answers}
    for rater in ('eligible_rater', 'unfamiliar_rater'):
        for trial in rater_order(load_public(target), 42, rater)[0]:
            chosen = by_id[trial.trial_id]['correct_character_id'] if rater == 'eligible_rater' else 'sherlock_holmes'
            submit_response(target, rater, trial.trial_id, chosen, 5 if rater == 'eligible_rater' else 1)
    result = analyze_benchmark(target)
    assert result['eligible_complete_raters'] == 1
    assert result['completed_raters'] == 2
    assert result['primary_familiar_complete']['accuracy'] == 1
    assert result['all_responses']['correct'] == 24
    assert result['per_character']['sherlock_holmes']['correct'] == 12
    assert result['confusion_matrix']['hercule_poirot']['sherlock_holmes'] == 6
    assert result['per_rater']['unfamiliar_rater']['accuracy'] == 1 / 3
    assert result['agreement']['overlapping_pairs'] == 18
    assert result['agreement']['pairwise_percentage'] == 1 / 3
    assert result['mean_confidence_incorrect'] == 1
    assert sum(result['responses_per_scenario'].values()) == 36


@pytest.mark.parametrize('where', ['single_run', 'all_runs', 'message_model'])
def test_frozen_model_mismatch_rejected(sources, where):
    root, _, runs = sources
    selected = runs if where == 'all_runs' else runs[:1]
    for run in selected:
        if where == 'message_model':
            messages = list(run.messages)
            messages[0] = messages[0].model_copy(update={'model': 'other-model'})
            run = run.model_copy(update={'messages': tuple(messages)})
        else:
            messages = tuple(message.model_copy(update={'model': 'other-model'}) for message in run.messages)
            run = run.model_copy(update={'model': 'other-model', 'configured_model': 'other-model', 'messages': messages})
        replace_run(root, run)
    with pytest.raises(ValueError):
        prepare(sources)
    assert not (root / 'evaluation' / 'benchmarks' / 'three_personas_v1').exists()


def test_order_enforced_under_lock(sources):
    from multi_agent_personalities.evaluation.benchmark_human import approve_review, load_public, rater_order, submit_familiarity, submit_response
    target = prepare(sources)
    approve_review(target, 'reviewer_test')
    trials = load_public(target)
    for rater in ('alice_test', 'bob_test'):
        submit_familiarity(target, rater, dict.fromkeys(IDS.values(), 2))
    order_a = rater_order(trials, 42, 'alice_test')[0]
    order_b = rater_order(trials, 42, 'bob_test')[0]
    assert order_a == rater_order(trials, 42, 'alice_test')[0] and order_a != order_b
    with pytest.raises(ValueError, match='out of order'):
        submit_response(target, 'alice_test', order_a[1].trial_id, 'sherlock_holmes', 3)
    assert not (target / 'responses.jsonl').exists()
    submit_response(target, 'alice_test', order_a[0].trial_id, 'sherlock_holmes', 3)
    before = (target / 'responses.jsonl').read_bytes()
    with pytest.raises(ValueError, match='already submitted'):
        submit_response(target, 'alice_test', order_a[0].trial_id, 'sherlock_holmes', 3)
    with pytest.raises(ValueError, match='out of order'):
        submit_response(target, 'alice_test', order_a[2].trial_id, 'sherlock_holmes', 3)
    assert (target / 'responses.jsonl').read_bytes() == before
    submit_response(target, 'alice_test', order_a[1].trial_id, 'sherlock_holmes', 3)
    submit_response(target, 'bob_test', order_b[0].trial_id, 'sherlock_holmes', 3)
    for item in order_a[2:]:
        submit_response(target, 'alice_test', item.trial_id, 'sherlock_holmes', 3)
    before = (target / 'responses.jsonl').read_bytes()
    with pytest.raises(ValueError):
        submit_response(target, 'alice_test', order_a[-1].trial_id, 'sherlock_holmes', 3)
    assert (target / 'responses.jsonl').read_bytes() == before


@pytest.mark.parametrize('mutation', ['answer_missing', 'answer_duplicate', 'answer_character', 'answer_scenario', 'answer_ref', 'manifest_model', 'manifest_source', 'manifest_hash', 'review_missing', 'review_mask', 'review_contradiction', 'public_metadata', 'public_blank'])
def test_review_rejects_inconsistent_artifacts(sources, mutation):
    from multi_agent_personalities.evaluation.benchmark_human import approve_review
    target = prepare(sources)
    public_path = target / 'trials_public.jsonl'
    answer_path = target / 'answer_key.jsonl'
    manifest_path = target / 'benchmark_manifest.json'
    review_path = target / 'leakage_review.json'
    answers = read_jsonl(answer_path)
    public = read_jsonl(public_path)
    manifest = json.loads(manifest_path.read_text())
    review = json.loads(review_path.read_text())
    if mutation == 'answer_missing': answers.pop()
    elif mutation == 'answer_duplicate': answers[-1] = answers[0].copy()
    elif mutation == 'answer_character': answers[0]['correct_character_id'] = 'unknown'
    elif mutation == 'answer_scenario': answers[0]['scenario_id'] = 'scenario_06' if answers[0]['scenario_id'] != 'scenario_06' else 'scenario_01'
    elif mutation == 'answer_ref': answers[0]['source_message_id'] = answers[1]['source_message_id']; answers[0]['source_run_id'] = answers[1]['source_run_id']
    elif mutation == 'manifest_model': manifest['model'] = 'wrong-model'
    elif mutation == 'manifest_source': manifest['sources'].pop('scenario_01')
    elif mutation == 'manifest_hash': manifest['personas']['layton']['sha256'] = '0' * 64
    elif mutation == 'review_missing': review['decisions'].pop()
    elif mutation == 'review_mask': review['decisions'][0]['mask_count'] += 1
    elif mutation == 'review_contradiction':
        selected = review['decisions'][0]
        review['decisions'].append({'scenario_id': selected['scenario_id'], 'run_id': selected['run_id'], 'message_id': selected['message_id'], 'decision': 'excluded', 'reason': 'duplicate_text'})
    elif mutation == 'public_metadata': public[0]['correct_character_id'] = 'sherlock_holmes'
    elif mutation == 'public_blank': public[0]['display_text'] = '   '
    answer_path.write_text(''.join(json.dumps(a) + '\n' for a in answers))
    public_path.write_text(''.join(json.dumps(p) + '\n' for p in public))
    manifest_path.write_text(json.dumps(manifest))
    review_path.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        approve_review(target, 'reviewer_test')
    assert not (target / 'review_approval.json').exists()
