"""Offline checks of prompt conditions, fingerprints, and run isolation."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import shutil

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models import ConversationRun, Persona
from multi_agent_personalities.pipeline import character_registry
from multi_agent_personalities.prompt_variants import (
    PROMPT_DIRECTORY, PROMPT_SOURCES, prompt_template_sha256,
)
from tests.test_agent_runtime import SpyProvider, call_runtime, make_message
from tests.test_live_conversation_service import RecordingProvider, run_live, REPOSITORY_ROOT


@pytest.mark.parametrize("slug", ["sherlock", "poirot", "layton", "kogoro"])
def test_dialogue_renders_complete_persona_and_literal_context(slug: str) -> None:
    config = character_registry(REPOSITORY_ROOT)[slug]
    source_before = config.live_persona_path.read_bytes()
    persona = Persona.model_validate_json(source_before)
    snapshot = persona.model_dump_json()
    history = [
        make_message(turn_index=0, speaker_name="First", text="{{ topic }} {conversation_history} {% broken %}"),
        make_message(turn_index=1, speaker_name="Second", text="A second observation.\nStill uncertain."),
    ]
    topic = "{{ conversation_history }} {persona_profile} {% invalid %}"
    provider = SpyProvider()
    call_runtime(persona, provider, history=history, turn_index=2,
                 topic=topic, prompt_variant="dialogue_v2")
    assert len(provider.calls) == 1
    prompt, task = provider.calls[0]
    assert task == "agent_reply"
    assert persona.description in prompt
    for field in ("speaking_style", "reasoning_style", "personality_traits", "behavior_rules", "example_messages"):
        assert all(value in prompt for value in getattr(persona, field))
    policy = (PROMPT_DIRECTORY / "conversation/dialogue_policy_v2.md").read_text().strip()
    assert policy in prompt
    assert topic in prompt
    first = f"[Turn 0] First: {history[0].text}"
    second = f"[Turn 1] Second: {history[1].text}"
    assert first in prompt and second in prompt
    assert prompt.index(first) < prompt.index(second)
    assert config.live_persona_path.read_bytes() == source_before
    assert persona.model_dump_json() == snapshot


def test_shared_dialogue_templates_have_no_character_scripts() -> None:
    text = "\n".join((PROMPT_DIRECTORY / name).read_text().lower()
                     for name in PROMPT_SOURCES["dialogue_v2"][1:])
    for name in ("sherlock", "holmes", "poirot", "layton", "kogoro", "mori", "mouri"):
        assert name not in text


@pytest.mark.parametrize("variant", ["baseline_v1", "dialogue_v2"])
def test_fingerprint_follows_documented_manifest_and_raw_bytes(variant: str, tmp_path: Path) -> None:
    shutil.copytree(PROMPT_DIRECTORY, tmp_path / "prompts")
    directory = tmp_path / "prompts"
    digest = sha256()
    for name in PROMPT_SOURCES[variant]:
        for data in (name.encode("utf-8"), (directory / name).read_bytes()):
            digest.update(len(data).to_bytes(8, "big") + data)
    original = prompt_template_sha256(variant, directory)
    assert original == digest.hexdigest() == prompt_template_sha256(variant)
    assert original == prompt_template_sha256(variant, directory)
    selected = directory / PROMPT_SOURCES[variant][-1]
    selected.write_bytes(selected.read_bytes() + b"\n")
    assert prompt_template_sha256(variant, directory) != original
    assert prompt_template_sha256("baseline_v1") != prompt_template_sha256("dialogue_v2")


def test_unselected_template_does_not_change_baseline_hash(tmp_path: Path) -> None:
    shutil.copytree(PROMPT_DIRECTORY, tmp_path / "prompts")
    directory = tmp_path / "prompts"
    (directory / "conversation/dialogue_policy_v2.md").write_text("Changed policy")
    assert prompt_template_sha256("baseline_v1", directory) == prompt_template_sha256("baseline_v1")
    assert prompt_template_sha256("dialogue_v2", directory) != prompt_template_sha256("dialogue_v2")


def test_variants_are_isolated_across_concurrent_and_sequential_runs(tmp_path: Path) -> None:
    def execute(index: int, variant: str):
        calls = []
        result = run_live(
            tmp_path / str(index), prompt_variant=variant,
            character_slugs=["kogoro", "layton", "poirot", "sherlock"], turn_count=8,
            factory=lambda model: RecordingProvider(model=model, calls=calls),
        )
        assert len(calls) == 8
        assert result.run.prompt_variant == variant
        assert result.run.prompt_template_sha256 == prompt_template_sha256(variant)
        assert [message.speaker_character_id for message in result.run.messages] == [
            "kogoro_mouri", "professor_layton", "hercule_poirot", "sherlock_holmes",
        ] * 2
        for turn, (_, _, prompt) in enumerate(calls):
            assert ("## Conversation policy — dialogue_v2" in prompt) == (variant == "dialogue_v2")
            for previous in result.run.messages[:turn]:
                assert f"[Turn {previous.turn_index}] {previous.speaker_name}: {previous.text}" in prompt
        restored = ConversationRun.model_validate_json((result.artifact_directory / "run.json").read_text())
        assert restored == result.run
        return result.run

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(execute, 0, "baseline_v1")
        second = pool.submit(execute, 1, "dialogue_v2")
        baseline, dialogue = first.result(), second.result()
    assert baseline.messages == dialogue.messages
    assert execute(2, "baseline_v1").messages == baseline.messages


@pytest.mark.parametrize("provider", ["mock", "copilot"])
def test_unknown_variant_rejected_before_any_generation(tmp_path: Path, provider: str) -> None:
    def factory(model):
        pytest.fail("provider must not be constructed")
    with pytest.raises(ValueError, match="unsupported prompt_variant"):
        run_live(tmp_path, provider=provider, copilot_model=None,
                 prompt_variant="unknown", factory=factory)
    assert not (tmp_path / "conversations").exists()


@pytest.mark.parametrize("updates", [
    {"prompt_variant": "unknown", "prompt_template_sha256": "a" * 64},
    {"prompt_variant": "dialogue_v2", "prompt_template_sha256": "invalid"},
    {"prompt_variant": "dialogue_v2", "prompt_template_sha256": None},
    {"prompt_variant": None, "prompt_template_sha256": "a" * 64},
])
def test_run_prompt_metadata_is_validated(tmp_path: Path, updates: dict) -> None:
    result = run_live(tmp_path, factory=lambda model: RecordingProvider(model=model, calls=[]))
    payload = result.run.model_dump()
    payload.update(updates)
    with pytest.raises(ValidationError):
        ConversationRun.model_validate(payload)


def test_mock_outputs_and_metadata_are_unchanged_between_variants(tmp_path: Path) -> None:
    runs = []
    for variant in ("baseline_v1", "dialogue_v2"):
        runs.append(run_live(
            tmp_path / variant, provider="mock", copilot_model=None,
            prompt_variant=variant, character_slugs=["sherlock", "poirot", "layton", "kogoro"],
            turn_count=8, factory=lambda model: pytest.fail("mock must not construct Copilot"),
        ).run)
    assert runs[0].messages == runs[1].messages
    assert runs[0].character_ids == runs[1].character_ids
    assert runs[0].provider == runs[1].provider == "mock"
    assert runs[0].model == runs[1].model == "mock-round-robin"
