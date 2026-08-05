"""Tests for immutable persona/provider runtime bindings."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from multi_agent_personalities.llm import MockProvider
from multi_agent_personalities.models import Persona
from multi_agent_personalities.simulation.participant import (
    ConversationParticipant,
    generate_participant_reply,
)


FIXED_TIME = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)


def persona() -> Persona:
    return Persona(
        character_id="alpha",
        display_name="Agent Alpha",
        description="Synthetic participant.",
        speaking_style=["Neutral"],
        reasoning_style=["Methodical"],
        personality_traits=["Test-only"],
        behavior_rules=["Use supplied context"],
        example_messages=["An example."],
    )


def response_file(tmp_path: Path) -> Path:
    path = tmp_path / "alpha-response.txt"
    path.write_text("response-from-alpha", encoding="utf-8")
    return path


def test_valid_binding_uses_persona_identity_and_is_immutable(tmp_path: Path) -> None:
    participant = ConversationParticipant(
        persona=persona(),
        provider=MockProvider({"agent_reply": response_file(tmp_path)}),
        provider_name="mock",
        model_name="mock-round-robin",
    )

    assert participant.character_id == "alpha"
    assert participant.display_name == "Agent Alpha"
    with pytest.raises(FrozenInstanceError):
        participant.provider_name = "changed"


@pytest.mark.parametrize(
    ("provider_name", "model_name", "error"),
    [
        (" ", "mock-round-robin", "provider_name must not be empty"),
        ("mock", " ", "model_name must not be empty"),
    ],
)
def test_invalid_binding_metadata_is_rejected(
    tmp_path: Path,
    provider_name: str,
    model_name: str,
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        ConversationParticipant(
            persona=persona(),
            provider=MockProvider({"agent_reply": response_file(tmp_path)}),
            provider_name=provider_name,
            model_name=model_name,
        )


class CountingMockProvider(MockProvider):
    def __init__(self, response_path: Path) -> None:
        super().__init__({"agent_reply": response_path})
        self.calls = 0

    def generate(self, prompt: str, *, task_name: str) -> str:
        self.calls += 1
        return super().generate(prompt, task_name=task_name)


def test_same_participant_can_generate_consecutive_bound_replies(
    tmp_path: Path,
) -> None:
    provider = CountingMockProvider(response_file(tmp_path))
    participant = ConversationParticipant(
        persona=persona(),
        provider=provider,
        provider_name="mock",
        model_name="mock-round-robin",
    )

    first = generate_participant_reply(
        participant=participant,
        history=[],
        topic="A synthetic case.",
        run_id="participant-binding-run",
        turn_index=0,
        timestamp=FIXED_TIME,
    )
    second = generate_participant_reply(
        participant=participant,
        history=[first],
        topic="A synthetic case.",
        run_id="participant-binding-run",
        turn_index=1,
        timestamp=FIXED_TIME,
    )

    assert [first.text, second.text] == [
        "response-from-alpha", "response-from-alpha",
    ]
    assert [first.speaker_character_id, second.speaker_character_id] == [
        "alpha", "alpha",
    ]
    assert [first.turn_index, second.turn_index] == [0, 1]
    assert provider.calls == 2
