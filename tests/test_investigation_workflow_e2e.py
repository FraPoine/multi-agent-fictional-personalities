"""Deterministic offline end-to-end coverage for the investigation workflow."""

import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from multi_agent_personalities.application import (
    FinalizationResult,
    GroupDecisionResult,
    GroupDiscussionResult,
    IndependentAnalysesResult,
    DeterministicInvestigationIdFactory,
    build_investigation_mock_bindings,
    create_group_decision,
    create_session,
    finalize_investigation,
    reveal_clue,
    run_group_discussion,
    run_independent_analyses,
)
from multi_agent_personalities.models import (
    InvestigationRoundStatus,
    InvestigationSession,
    InvestigationStatus,
    Persona,
)
from multi_agent_personalities.simulation.participant import ConversationParticipant


ROOT = Path(__file__).resolve().parents[1]
PARTICIPANT_IDS = ("sherlock_holmes", "hercule_poirot")
FIXED_TIME = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
SEED = 42
TURN_COUNT = 2


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any accidental live-provider or download path fail immediately."""

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)


def participant_bindings() -> tuple[
    ConversationParticipant, ConversationParticipant
]:
    mock = build_investigation_mock_bindings()
    personas = tuple(
        Persona.model_validate_json(
            (ROOT / "tests" / "fixtures" / filename).read_text(encoding="utf-8")
        )
        for filename in (
            "sherlock_persona_response.json",
            "poirot_persona_response.json",
        )
    )
    return tuple(
        ConversationParticipant(
            persona=persona,
            provider=mock.participant_providers[persona.character_id],
            provider_name="mock",
        )
        for persona in personas
    )  # type: ignore[return-value]


@dataclass(frozen=True)
class WorkflowTrace:
    created: InvestigationSession
    round_one_revealed: InvestigationSession
    round_one_analyses: IndependentAnalysesResult
    round_one_discussion: GroupDiscussionResult
    round_one_decision: GroupDecisionResult
    round_two_revealed: InvestigationSession
    round_two_analyses: IndependentAnalysesResult
    round_two_discussion: GroupDiscussionResult
    round_two_decision: GroupDecisionResult
    finalization: FinalizationResult


def run_two_round_workflow() -> WorkflowTrace:
    """Call every public workflow operation explicitly with fixed inputs."""
    factory = DeterministicInvestigationIdFactory(1)
    mock = build_investigation_mock_bindings()

    created = create_session(
        id_factory=factory,
        introduction="A researcher disappears from a locked archive room.",
        participant_ids=PARTICIPANT_IDS,
    )
    round_one_revealed = reveal_clue(
        created,
        clue_text="The archive-room window was found open.",
        id_factory=factory,
    )
    round_one_analyses = run_independent_analyses(
        round_one_revealed,
        participant_bindings=participant_bindings(),
        id_factory=factory,
    )
    round_one_discussion = run_group_discussion(
        round_one_analyses.session,
        participant_bindings=participant_bindings(),
        id_factory=factory,
        turn_count=TURN_COUNT,
        seed=SEED,
        timestamp=FIXED_TIME,
    )
    round_one_decision = create_group_decision(
        round_one_discussion.session,
        decision_provider=mock.decision_provider,
        id_factory=factory,
    )

    round_two_revealed = reveal_clue(
        round_one_decision.session,
        clue_text="The wet soil below the window contained no footprints.",
        id_factory=factory,
    )
    round_two_analyses = run_independent_analyses(
        round_two_revealed,
        participant_bindings=participant_bindings(),
        id_factory=factory,
    )
    round_two_discussion = run_group_discussion(
        round_two_analyses.session,
        participant_bindings=participant_bindings(),
        id_factory=factory,
        turn_count=TURN_COUNT,
        seed=SEED,
        timestamp=FIXED_TIME,
    )
    round_two_decision = create_group_decision(
        round_two_discussion.session,
        decision_provider=mock.decision_provider,
        id_factory=factory,
    )
    finalization = finalize_investigation(
        round_two_decision.session,
        final_theory_provider=mock.final_theory_provider,
        id_factory=factory,
    )
    return WorkflowTrace(
        created=created,
        round_one_revealed=round_one_revealed,
        round_one_analyses=round_one_analyses,
        round_one_discussion=round_one_discussion,
        round_one_decision=round_one_decision,
        round_two_revealed=round_two_revealed,
        round_two_analyses=round_two_analyses,
        round_two_discussion=round_two_discussion,
        round_two_decision=round_two_decision,
        finalization=finalization,
    )


def test_two_round_investigation_workflow_is_explicit_deterministic_and_offline(
    tmp_path: Path,
) -> None:
    before_files = tuple(tmp_path.iterdir())
    first = run_two_round_workflow()

    created = first.created
    assert created.status is InvestigationStatus.ACTIVE
    assert created.clues == created.rounds == created.analyses == ()
    assert created.hypotheses == created.decisions == ()
    assert created.final_theory is None

    round_one_revealed = first.round_one_revealed
    clue_one_id = "session_001_clue_0001"
    clue_two_id = "session_001_clue_0002"
    round_one_visibility = (clue_one_id,)
    assert len(round_one_revealed.clues) == len(round_one_revealed.rounds) == 1
    assert round_one_revealed.clues[0].reveal_order == 0
    assert round_one_revealed.rounds[0].round_index == 1
    assert round_one_revealed.rounds[0].status is (
        InvestigationRoundStatus.AWAITING_ANALYSES
    )
    assert round_one_revealed.rounds[0].visible_clue_ids == round_one_visibility
    round_one_clue_snapshot = round_one_revealed.clues[0]

    analysed_one = first.round_one_analyses
    assert len(analysed_one.generations) == len(PARTICIPANT_IDS)
    assert tuple(item.agent_id for item in analysed_one.session.analyses) == (
        PARTICIPANT_IDS
    )
    assert all(
        item.round_id == "session_001_round_0001"
        and item.visible_clue_ids == round_one_visibility
        and all(
            evidence.clue_id in round_one_visibility for evidence in item.evidence
        )
        for item in analysed_one.session.analyses
    )
    assert all(
        item.generation.metadata.provider == "mock"
        and item.generation.metadata.finish_reason == "completed"
        for item in analysed_one.generations
    )
    assert analysed_one.session.rounds[0].status is (
        InvestigationRoundStatus.AWAITING_DISCUSSION
    )

    discussed_one = first.round_one_discussion
    discussion_one = discussed_one.conversation_run
    assert discussed_one.session.rounds[0].discussion_run == discussion_one
    assert discussion_one.status == "completed"
    assert discussion_one.run_id == "session_001_round_0001_discussion"
    assert len(discussion_one.messages) == TURN_COUNT
    assert tuple(item.speaker_character_id for item in discussion_one.messages) == (
        PARTICIPANT_IDS
    )
    assert tuple(item.turn_index for item in discussion_one.messages) == (0, 1)
    assert all(
        item.generation_metadata is not None
        and item.generation_metadata.provider == item.provider == "mock"
        and item.generation_metadata.model == item.model
        for item in discussion_one.messages
    )
    assert discussed_one.session.rounds[0].status is (
        InvestigationRoundStatus.AWAITING_DECISION
    )

    paused_one = first.round_one_decision
    assert len(paused_one.session.decisions) == 1
    assert paused_one.decision.round_id == "session_001_round_0001"
    assert paused_one.session.rounds[0].decision_id == paused_one.decision.decision_id
    assert paused_one.session.rounds[0].status is InvestigationRoundStatus.COMPLETED
    assert paused_one.session.status is InvestigationStatus.ACTIVE
    assert paused_one.session.final_theory is None
    assert len(paused_one.session.clues) == len(paused_one.session.rounds) == 1
    assert paused_one.generation.generation.metadata.provider == "mock"
    assert paused_one.generation.generation.metadata.finish_reason == "completed"

    round_one_json = paused_one.session.rounds[0].model_dump_json()
    round_one_analyses = paused_one.session.analyses
    round_one_discussion = paused_one.session.rounds[0].discussion_run
    round_two_revealed = first.round_two_revealed
    round_two_visibility = (clue_one_id, clue_two_id)
    assert len(round_two_revealed.clues) == len(round_two_revealed.rounds) == 2
    assert round_two_revealed.clues[0] == round_one_clue_snapshot
    assert round_two_revealed.clues[1].reveal_order == 1
    assert round_two_revealed.rounds[1].round_index == 2
    assert round_two_revealed.rounds[1].status is (
        InvestigationRoundStatus.AWAITING_ANALYSES
    )
    assert round_two_revealed.rounds[0].visible_clue_ids == round_one_visibility
    assert round_two_revealed.rounds[1].visible_clue_ids == round_two_visibility

    analysed_two = first.round_two_analyses
    new_analyses = analysed_two.session.analyses[2:]
    assert analysed_two.session.analyses[:2] == round_one_analyses
    assert tuple(item.agent_id for item in new_analyses) == PARTICIPANT_IDS
    assert all(
        item.round_id == "session_001_round_0002"
        and item.visible_clue_ids == round_two_visibility
        and all(
            evidence.clue_id in round_two_visibility for evidence in item.evidence
        )
        for item in new_analyses
    )
    assert all(item.visible_clue_ids == round_one_visibility for item in round_one_analyses)
    assert all(item.generation.metadata.provider == "mock" for item in analysed_two.generations)
    assert analysed_two.session.rounds[1].analysis_ids == (
        "session_001_analysis_sherlock_holmes_0002",
        "session_001_analysis_hercule_poirot_0002",
    )

    discussed_two = first.round_two_discussion
    discussion_two = discussed_two.conversation_run
    assert discussed_two.session.rounds[0].model_dump_json() == round_one_json
    assert discussed_two.session.rounds[0].discussion_run == round_one_discussion
    assert discussed_two.session.rounds[1].discussion_run == discussion_two
    assert discussion_two.run_id == "session_001_round_0002_discussion"
    assert tuple(item.speaker_character_id for item in discussion_two.messages) == (
        PARTICIPANT_IDS
    )
    assert tuple(item.turn_index for item in discussion_two.messages) == (0, 1)
    assert discussed_two.session.rounds[0].status is InvestigationRoundStatus.COMPLETED
    assert discussed_two.session.rounds[1].status is (
        InvestigationRoundStatus.AWAITING_DECISION
    )

    paused_two = first.round_two_decision
    assert len(paused_two.session.decisions) == 2
    assert paused_two.decision.round_id == "session_001_round_0002"
    assert paused_two.session.rounds[1].decision_id == paused_two.decision.decision_id
    assert all(
        item.status is InvestigationRoundStatus.COMPLETED
        for item in paused_two.session.rounds
    )
    assert paused_two.session.status is InvestigationStatus.ACTIVE
    assert paused_two.session.final_theory is None
    assert len(paused_two.session.rounds) == len(paused_two.session.clues) == 2
    assert paused_two.generation.generation.metadata.provider == "mock"

    before_finalization = paused_two.session
    completed = first.finalization.session
    final_theory = first.finalization.final_theory
    assert final_theory.final_theory_id == "session_001_final_theory"
    assert final_theory == completed.final_theory
    assert completed.status is InvestigationStatus.COMPLETED
    assert completed.rounds == before_finalization.rounds
    assert completed.clues == before_finalization.clues
    assert completed.analyses == before_finalization.analyses
    assert completed.hypotheses == before_finalization.hypotheses
    assert completed.decisions == before_finalization.decisions
    assert set(final_theory.hypothesis_ids) <= {
        item.hypothesis_id for item in completed.hypotheses
    }
    assert all(
        item.clue_id in round_two_visibility for item in final_theory.evidence
    )
    assert first.finalization.generation.generation.metadata.provider == "mock"
    assert first.finalization.generation.generation.metadata.finish_reason == "completed"

    serialized = completed.model_dump_json()
    restored = InvestigationSession.model_validate_json(serialized)
    assert restored == completed
    assert restored.final_theory == final_theory
    assert all(item.status is InvestigationRoundStatus.COMPLETED for item in restored.rounds)
    assert tuple(
        tuple(message.turn_index for message in item.discussion_run.messages)
        for item in restored.rounds
    ) == ((0, 1), (0, 1))

    second = run_two_round_workflow()
    assert second == first
    assert second.finalization.session.model_dump_json() == serialized
    assert tuple(tmp_path.iterdir()) == before_files
