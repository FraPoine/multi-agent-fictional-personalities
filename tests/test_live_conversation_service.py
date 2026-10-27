"""Offline tests for provider-selectable conversation orchestration."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from multi_agent_personalities.application import run_conversation
from multi_agent_personalities.models import (
    ConversationRun,
    GenerationMetadata,
    GenerationResult,
    Message,
    TokenUsage,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
TOPIC = "A coded warning vanished from a locked study."


class RecordingProvider:
    def __init__(
        self,
        *,
        model: str | None,
        calls: list[tuple[str | None, str, str]],
        reported_model: str | None = "gpt-test",
        failure: Exception | None = None,
    ) -> None:
        self.model = model
        self.calls = calls
        self.reported_model = reported_model
        self.failure = failure

    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        self.calls.append((self.model, task_name, prompt))
        if self.failure is not None:
            raise self.failure
        speaker = (
            "sherlock" if "Sherlock Holmes" in prompt else "poirot"
        )
        return GenerationResult(
            text=f"{speaker}-reply-{len(self.calls)}",
            metadata=GenerationMetadata(
                provider="copilot",
                model=self.reported_model,
                usage=TokenUsage(input_tokens=20, output_tokens=5),
                finish_reason="stop",
                request_id=f"request-{len(self.calls)}",
            ),
        )


def run_live(
    output_root: Path,
    *,
    factory,
    **overrides: object,
):
    arguments = {
        "character_slugs": ["sherlock", "poirot"],
        "topic": TOPIC,
        "turn_count": 4,
        "provider": "copilot",
        "copilot_model": "gpt-test",
        "seed": 17,
        "output_root": output_root,
        "project_root": REPOSITORY_ROOT,
        "run_id": "live_service_run",
        "timestamp": FIXED_TIME,
        "_copilot_provider_factory": factory,
    }
    arguments.update(overrides)
    return run_conversation(**arguments)


def test_live_conversation_alternates_personas_and_receives_complete_history(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str | None, str, str]] = []
    providers: list[RecordingProvider] = []

    def factory(model: str | None) -> RecordingProvider:
        provider = RecordingProvider(model=model, calls=calls)
        providers.append(provider)
        return provider

    result = run_live(tmp_path, factory=factory)

    assert len(providers) == 2
    assert [call[0] for call in calls] == ["gpt-test"] * 4
    assert [call[1] for call in calls] == ["agent_reply"] * 4
    assert [message.speaker_character_id for message in result.run.messages] == [
        "sherlock_holmes",
        "hercule_poirot",
        "sherlock_holmes",
        "hercule_poirot",
    ]
    sherlock_profile = calls[0][2].split("## Conversation topic")[0]
    poirot_profile = calls[1][2].split("## Conversation topic")[0]
    assert "Sherlock Holmes" in sherlock_profile
    assert "Hercule Poirot" not in sherlock_profile
    assert "Hercule Poirot" in poirot_profile
    assert "Sherlock Holmes" not in poirot_profile
    assert "No previous messages." in calls[0][2]
    for turn_index, (_, _, prompt) in enumerate(calls):
        for prior in result.run.messages[:turn_index]:
            assert prior.text in prompt


def test_live_metadata_and_artifacts_are_preserved(tmp_path: Path) -> None:
    calls: list[tuple[str | None, str, str]] = []
    result = run_live(
        tmp_path,
        factory=lambda model: RecordingProvider(model=model, calls=calls),
    )

    assert result.run.provider == "copilot"
    assert result.run.model == "gpt-test"
    assert result.run.seed == 17
    assert all(
        message.provider == "copilot"
        and message.model == "gpt-test"
        and message.generation_metadata is not None
        and message.generation_metadata.usage == TokenUsage(
            input_tokens=20, output_tokens=5
        )
        and message.generation_metadata.request_id is not None
        for message in result.run.messages
    )
    assert {path.name for path in result.artifact_paths} == {
        "run.json", "messages.jsonl", "transcript.md",
    }
    persisted = ConversationRun.model_validate_json(
        (result.artifact_directory / "run.json").read_text(encoding="utf-8")
    )
    messages = [
        Message.model_validate_json(line)
        for line in (result.artifact_directory / "messages.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert persisted == result.run
    assert messages == list(result.run.messages)
    assert "**Provider:** copilot" in result.transcript_path.read_text(
        encoding="utf-8"
    )


def test_selected_model_is_preserved_when_provider_omits_metadata(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str | None, str, str]] = []
    result = run_live(
        tmp_path,
        factory=lambda model: RecordingProvider(
            model=model, calls=calls, reported_model=None
        ),
    )
    assert all(call[0] == "gpt-test" for call in calls)
    assert result.run.model == "gpt-test"
    assert all(message.model == "gpt-test" for message in result.run.messages)
    assert all(
        message.generation_metadata is not None
        and message.generation_metadata.model is None
        for message in result.run.messages
    )


def test_sdk_default_model_is_recorded_only_when_reported(tmp_path: Path) -> None:
    calls: list[tuple[str | None, str, str]] = []
    result = run_live(
        tmp_path,
        copilot_model=None,
        factory=lambda model: RecordingProvider(
            model=model, calls=calls, reported_model="sdk-default-model"
        ),
    )
    assert all(call[0] is None for call in calls)
    assert result.run.model == "sdk-default-model"


def test_reported_model_mismatch_fails_without_artifacts(tmp_path: Path) -> None:
    calls: list[tuple[str | None, str, str]] = []
    with pytest.raises(ValueError, match="declared model does not match"):
        run_live(
            tmp_path,
            factory=lambda model: RecordingProvider(
                model=model, calls=calls, reported_model="different-model"
            ),
        )
    assert len(calls) == 1
    assert not (tmp_path / "conversations").exists()


def test_provider_failure_does_not_persist_incomplete_artifacts(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str | None, str, str]] = []
    failure = RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        run_live(
            tmp_path,
            factory=lambda model: RecordingProvider(
                model=model, calls=calls, failure=failure
            ),
        )

    assert len(calls) == 1
    assert not (tmp_path / "conversations").exists()


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"provider": "unknown"}, "unsupported provider"),
        ({"topic": "  "}, "topic must not be empty"),
        ({"turn_count": 1}, "between 2 and 12"),
        ({"turn_count": 13}, "between 2 and 12"),
        ({"turn_count": True}, "must be an integer"),
        ({"copilot_model": " "}, "copilot_model must not be empty"),
        ({"character_slugs": ["sherlock"]}, "at least two"),
        ({"character_slugs": ["sherlock", "unknown"]}, "unsupported character"),
        ({"run_id": "invalid/run"}, "run_id"),
    ],
)
def test_invalid_input_fails_before_provider_construction(
    tmp_path: Path,
    overrides: dict[str, object],
    error: str,
) -> None:
    constructed = 0

    def factory(model: str | None) -> RecordingProvider:
        nonlocal constructed
        constructed += 1
        return RecordingProvider(model=model, calls=[])

    with pytest.raises(ValueError, match=error):
        run_live(tmp_path, factory=factory, **overrides)
    assert constructed == 0
    assert not (tmp_path / "conversations").exists()


def test_general_api_preserves_mock_defaults_and_behavior(tmp_path: Path) -> None:
    result = run_conversation(
        character_slugs=["sherlock", "poirot"],
        topic=TOPIC,
        turn_count=2,
        output_root=tmp_path,
        project_root=REPOSITORY_ROOT,
        run_id="general_mock_run",
        timestamp=FIXED_TIME,
    )
    assert result.run.provider == "mock"
    assert result.run.model == "mock-round-robin"
    assert [message.speaker_character_id for message in result.run.messages] == [
        "sherlock_holmes", "hercule_poirot",
    ]


def test_mock_rejects_copilot_model_before_generation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="only valid"):
        run_conversation(
            character_slugs=["sherlock", "poirot"],
            topic=TOPIC,
            turn_count=2,
            provider="mock",
            copilot_model="gpt-test",
            output_root=tmp_path,
            project_root=REPOSITORY_ROOT,
        )
