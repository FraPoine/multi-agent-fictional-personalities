"""Application and conversation integration tests for Lead/Visit sessions."""

from datetime import datetime, timezone

import pytest

from multi_agent_personalities.application import (
    investigation_visit_service as visit_service,
)
from multi_agent_personalities.application import (
    DeterministicInvestigationIdFactory,
    build_lead_discussion_context,
    continue_lead_discussion,
    create_session,
    project_lead_conversation,
    reveal_information,
    visit_lead,
)
from multi_agent_personalities.models import (
    ConversationRun,
    GenerationMetadata,
    GenerationResult,
    Persona,
)
from multi_agent_personalities.simulation import ConversationParticipant


NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


class RecordingProvider:
    def __init__(self, name: str, response: str) -> None:
        self.name = name
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        self.prompts.append(prompt)
        return GenerationResult(
            text=self.response,
            metadata=GenerationMetadata(provider="recording", model="model-v1"),
        )


class FailingProvider(RecordingProvider):
    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        self.prompts.append(prompt)
        raise RuntimeError("provider failed")


def participant(character_id: str, provider: RecordingProvider) -> ConversationParticipant:
    persona = Persona(
        character_id=character_id,
        display_name=character_id.title(),
        description=f"Description for {character_id}.",
        speaking_style=["Precise"],
        reasoning_style=["Methodical"],
        personality_traits=["Observant"],
        behavior_rules=["Discuss supplied evidence only"],
        example_messages=["An example."],
    )
    return ConversationParticipant(
        persona=persona,
        provider=provider,
        provider_name="recording",
        model_name="model-v1",
    )


def bindings(
    *, failing_first: bool = False
) -> tuple[ConversationParticipant, ConversationParticipant]:
    first_provider = (
        FailingProvider("alpha", "unused")
        if failing_first
        else RecordingProvider("alpha", "Alpha reply")
    )
    return (
        participant("alpha", first_provider),
        participant("beta", RecordingProvider("beta", "Beta reply")),
    )


def new_session(sequence: int = 1):
    factory = DeterministicInvestigationIdFactory(sequence)
    session = create_session(
        id_factory=factory,
        introduction="The clock stopped at midnight.",
        participant_ids=("alpha", "beta"),
    )
    return session, factory


def test_application_allows_a_b_a_c_a_without_reasoning_gates() -> None:
    session, factory = new_session()
    session = visit_lead(session, id_factory=factory, label="A", kind="person")
    lead_a = session.leads[0].lead_id
    session = visit_lead(session, id_factory=factory, label="B", kind="place")
    lead_b = session.leads[1].lead_id
    session = visit_lead(session, id_factory=factory, lead_id=lead_a)
    session = visit_lead(session, id_factory=factory, label="C", kind="topic")
    lead_c = session.leads[2].lead_id
    session = visit_lead(session, id_factory=factory, lead_id=lead_a)

    assert [item.lead_id for item in session.visits] == [
        lead_a, lead_b, lead_a, lead_c, lead_a
    ]
    assert [item.visit_id for item in session.visits] == [
        f"session_001_visit_{index:04d}" for index in range(1, 6)
    ]
    assert session.analyses == session.decisions == ()


def test_unknown_or_foreign_lead_revisit_is_atomic() -> None:
    session, factory = new_session()
    original_json = session.model_dump_json()

    with pytest.raises(ValueError, match="unknown lead_id"):
        visit_lead(session, id_factory=factory, lead_id="session_002_lead_0001")

    assert session.model_dump_json() == original_json


def test_explicit_multiple_information_disclosure_is_global_and_atomic() -> None:
    session, factory = new_session()
    session = visit_lead(session, id_factory=factory, label="A", kind="person")
    visit_a = session.visits[-1]
    session = reveal_information(
        session,
        visit_id=visit_a.visit_id,
        information_texts=("A wore red gloves.", "A arrived before noon."),
        id_factory=factory,
    )
    session = visit_lead(session, id_factory=factory, label="B", kind="place")
    session = reveal_information(
        session,
        visit_id=session.visits[-1].visit_id,
        information_texts=("B's window was open.",),
        id_factory=factory,
    )

    assert [item.information_id for item in session.revealed_information] == [
        "session_001_info_0001",
        "session_001_info_0002",
        "session_001_info_0003",
    ]
    assert [item.text for item in session.revealed_information] == [
        "A wore red gloves.", "A arrived before noon.", "B's window was open."
    ]

    frozen = session.model_dump_json()
    with pytest.raises(ValueError, match="unknown visit_id"):
        reveal_information(
            session,
            visit_id="session_002_visit_0001",
            information_texts=("Invalid.",),
            id_factory=factory,
        )
    with pytest.raises(ValueError, match="information text"):
        reveal_information(
            session,
            visit_id=session.visits[-1].visit_id,
            information_texts=("valid", " "),
            id_factory=factory,
        )
    assert session.model_dump_json() == frozen


def test_a_b_a_discussions_are_bounded_repeatable_and_explicitly_contextual() -> None:
    session, factory = new_session()
    participants = bindings()
    session = visit_lead(session, id_factory=factory, label="A", kind="person")
    lead_a = session.leads[0].lead_id
    visit_a1 = session.visits[-1]
    session = reveal_information(
        session,
        visit_id=visit_a1.visit_id,
        information_texts=("A information.",),
        id_factory=factory,
    )
    a1 = continue_lead_discussion(
        session,
        visit_id=visit_a1.visit_id,
        participant_bindings=participants,
        id_factory=factory,
        turn_count=2,
        timestamp=NOW,
    )
    session = a1.session
    frozen_a1 = a1.conversation_run.model_dump_json()

    session = visit_lead(session, id_factory=factory, label="B", kind="place")
    visit_b = session.visits[-1]
    session = reveal_information(
        session,
        visit_id=visit_b.visit_id,
        information_texts=("B information.",),
        id_factory=factory,
    )
    b1 = continue_lead_discussion(
        session,
        visit_id=visit_b.visit_id,
        participant_bindings=participants,
        id_factory=factory,
        turn_count=2,
        timestamp=NOW,
    )
    session = visit_lead(b1.session, id_factory=factory, lead_id=lead_a)
    visit_a2 = session.visits[-1]

    context = build_lead_discussion_context(session, visit_id=visit_a2.visit_id)
    assert context.index("A information.") < context.index("B information.")
    assert "The clock stopped at midnight." in context
    assert f"[{lead_a}] A (kind: person)" in context
    assert "Alpha: Alpha reply" in context
    assert "Beta: Beta reply" in context

    a2_first = continue_lead_discussion(
        session,
        visit_id=visit_a2.visit_id,
        participant_bindings=participants,
        id_factory=factory,
        turn_count=2,
        timestamp=NOW,
    )
    a2_second = continue_lead_discussion(
        a2_first.session,
        visit_id=visit_a2.visit_id,
        participant_bindings=participants,
        id_factory=factory,
        turn_count=2,
        timestamp=NOW,
    )

    assert a1.conversation_run.run_id == (
        "session_001_visit_0001_discussion_0001"
    )
    assert b1.conversation_run.run_id == (
        "session_001_visit_0002_discussion_0001"
    )
    assert a2_first.conversation_run.run_id == (
        "session_001_visit_0003_discussion_0001"
    )
    assert a2_second.conversation_run.run_id == (
        "session_001_visit_0003_discussion_0002"
    )
    assert a1.conversation_run.model_dump_json() == frozen_a1
    assert all(item.status == "completed" for item in a2_second.session.conversation_runs)
    assert all(len(item.messages) == 2 for item in a2_second.session.conversation_runs)
    assert a2_first.context == context
    assert "A information." in participants[0].provider.prompts[-1]
    assert "B information." in participants[0].provider.prompts[-1]

    projected = project_lead_conversation(a2_second.session, lead_a)
    assert [item.run_id for item in projected] == [
        a1.conversation_run.run_id,
        a1.conversation_run.run_id,
        a2_first.conversation_run.run_id,
        a2_first.conversation_run.run_id,
        a2_second.conversation_run.run_id,
        a2_second.conversation_run.run_id,
    ]


def test_provider_failure_does_not_attach_a_partial_segment() -> None:
    session, factory = new_session()
    session = visit_lead(session, id_factory=factory, label="A", kind="person")
    frozen = session.model_dump_json()

    with pytest.raises(RuntimeError, match="provider failed"):
        continue_lead_discussion(
            session,
            visit_id=session.visits[-1].visit_id,
            participant_bindings=bindings(failing_first=True),
            id_factory=factory,
            turn_count=2,
            timestamp=NOW,
        )

    assert session.model_dump_json() == frozen
    assert session.conversation_runs == ()


def test_invalid_returned_conversation_run_is_rejected_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, factory = new_session()
    session = visit_lead(session, id_factory=factory, label="A", kind="person")
    frozen = session.model_dump_json()
    invalid_run = ConversationRun(
        run_id="session_001_visit_0001_discussion_0001",
        topic="Invalid participants",
        character_ids=("foreign_a", "foreign_b"),
        turn_count=1,
        seed=42,
        provider="recording",
        model="model-v1",
        created_at=NOW,
        status="running",
    )
    monkeypatch.setattr(
        visit_service, "simulate_chat", lambda **kwargs: invalid_run
    )

    with pytest.raises(ValueError, match="participants must match"):
        continue_lead_discussion(
            session,
            visit_id=session.visits[-1].visit_id,
            participant_bindings=bindings(),
            id_factory=factory,
            turn_count=2,
            timestamp=NOW,
        )

    assert session.model_dump_json() == frozen
    assert session.conversation_runs == ()


def test_sessions_have_isolated_lead_context_and_run_namespaces() -> None:
    first, first_factory = new_session(1)
    second, second_factory = new_session(2)
    first = visit_lead(first, id_factory=first_factory, label="First", kind="topic")
    second = visit_lead(second, id_factory=second_factory, label="Second", kind="topic")
    first = reveal_information(
        first,
        visit_id=first.visits[-1].visit_id,
        information_texts=("Only first.",),
        id_factory=first_factory,
    )
    second_result = continue_lead_discussion(
        second,
        visit_id=second.visits[-1].visit_id,
        participant_bindings=bindings(),
        id_factory=second_factory,
        turn_count=2,
        timestamp=NOW,
    )

    assert "Only first." not in second_result.context
    assert second_result.conversation_run.run_id.startswith("session_002_")
    assert first.conversation_runs == ()
