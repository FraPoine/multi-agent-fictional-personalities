"""Tests for immutable investigation building-block models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models import (
    AgentAnalysis,
    Clue,
    ConversationRun,
    EvidenceReference,
    EvidenceRelation,
    GroupDecision,
    GroupDecisionType,
    Hypothesis,
    HypothesisStatus,
    InvestigationRound,
    InvestigationRoundStatus,
    validate_unique_clue_ids,
)


def make_clue(clue_id: str = "clue_001", reveal_order: int = 0) -> Clue:
    return Clue(
        clue_id=clue_id,
        text="  A muddy footprint points toward the window.  ",
        reveal_order=reveal_order,
    )


def test_valid_clue_accepts_zero_and_preserves_text() -> None:
    clue = make_clue()

    assert clue.clue_id == "clue_001"
    assert clue.text == "  A muddy footprint points toward the window.  "
    assert clue.reveal_order == 0


@pytest.mark.parametrize(
    ("relation", "serialized"),
    [
        (EvidenceRelation.SUPPORTS, "supports"),
        (EvidenceRelation.CONTRADICTS, "contradicts"),
        (EvidenceRelation.CONTEXT, "context"),
    ],
)
def test_all_evidence_relations_are_supported(
    relation: EvidenceRelation,
    serialized: str,
) -> None:
    reference = EvidenceReference(clue_id="clue_001", relation=relation)

    assert reference.relation is relation
    assert reference.model_dump(mode="json")["relation"] == serialized


@pytest.mark.parametrize("model", [Clue, EvidenceReference])
@pytest.mark.parametrize("clue_id", ["", "   "])
def test_empty_and_whitespace_only_ids_are_rejected(
    model: type[Clue] | type[EvidenceReference],
    clue_id: str,
) -> None:
    payload: dict[str, object]
    if model is Clue:
        payload = {"clue_id": clue_id, "text": "Revealed", "reveal_order": 0}
    else:
        payload = {"clue_id": clue_id, "relation": "context"}

    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("text", ["", " \t\n "])
def test_empty_and_whitespace_only_clue_text_is_rejected(text: str) -> None:
    with pytest.raises(ValidationError):
        Clue(clue_id="clue_001", text=text, reveal_order=0)


@pytest.mark.parametrize("reveal_order", [-1, True, False])
def test_invalid_reveal_order_is_rejected(reveal_order: object) -> None:
    with pytest.raises(ValidationError):
        Clue(
            clue_id="clue_001",
            text="Revealed information",
            reveal_order=reveal_order,
        )


def test_unsupported_evidence_relation_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidenceReference(clue_id="clue_001", relation="irrelevant")


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            Clue,
            {
                "clue_id": "clue_001",
                "text": "Revealed",
                "reveal_order": 0,
                "deduction": "The suspect fled",
            },
        ),
        (
            EvidenceReference,
            {
                "clue_id": "clue_001",
                "relation": "supports",
                "text": "Duplicated clue text",
            },
        ),
    ],
)
def test_extra_fields_are_forbidden(
    model: type[Clue] | type[EvidenceReference],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_models_are_frozen() -> None:
    clue = make_clue()
    reference = EvidenceReference(
        clue_id="clue_001",
        relation=EvidenceRelation.SUPPORTS,
    )

    with pytest.raises(ValidationError):
        clue.text = "Changed"
    with pytest.raises(ValidationError):
        reference.relation = EvidenceRelation.CONTEXT


def test_json_serialization_round_trips() -> None:
    clue = make_clue(reveal_order=2)
    reference = EvidenceReference(
        clue_id=clue.clue_id,
        relation=EvidenceRelation.CONTRADICTS,
    )

    assert Clue.model_validate_json(clue.model_dump_json()) == clue
    assert EvidenceReference.model_validate_json(
        reference.model_dump_json()
    ) == reference


def test_duplicate_clue_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        validate_unique_clue_ids([make_clue(), make_clue(reveal_order=1)])


def test_unique_clue_order_is_preserved_and_result_is_a_tuple() -> None:
    clues = [
        make_clue("clue_002", reveal_order=1),
        make_clue("clue_001", reveal_order=0),
    ]

    result = validate_unique_clue_ids(clues)

    assert isinstance(result, tuple)
    assert [clue.clue_id for clue in result] == ["clue_002", "clue_001"]
    assert validate_unique_clue_ids([]) == ()


def test_unique_clue_validation_does_not_mutate_input() -> None:
    clues = [make_clue("clue_001"), make_clue("clue_002", reveal_order=1)]
    original = list(clues)

    result = validate_unique_clue_ids(clues)

    assert clues == original
    assert result == tuple(original)
    assert result is not clues


def make_evidence(
    relation: EvidenceRelation = EvidenceRelation.SUPPORTS,
) -> EvidenceReference:
    return EvidenceReference(clue_id="clue_001", relation=relation)


def analysis_context() -> dict[str, object]:
    return {
        "session_id": "session_001",
        "round_id": "round_001",
        "visible_clue_ids": ["clue_001"],
    }


def round_owned_context() -> dict[str, object]:
    return {"session_id": "session_001", "round_id": "round_001"}


def test_valid_analysis_keeps_facts_deductions_and_leads_separate() -> None:
    analysis = AgentAnalysis(
        analysis_id="analysis_001",
        session_id="session_001",
        round_id="round_001",
        agent_id="sherlock",
        visible_clue_ids=("clue_001",),
        facts=("The window is open.",),
        deductions=("The intruder used the window.",),
        evidence=(make_evidence(),),
        proposed_leads=("Inspect the garden.",),
    )

    assert analysis.agent_id == "sherlock"
    assert analysis.facts == ("The window is open.",)
    assert analysis.deductions == ("The intruder used the window.",)
    assert analysis.proposed_leads == ("Inspect the garden.",)
    assert not isinstance(analysis, GroupDecision)


@pytest.mark.parametrize("agent_id", ["", "   "])
def test_analysis_requires_non_empty_agent_id(agent_id: str) -> None:
    with pytest.raises(ValidationError):
        AgentAnalysis(
            analysis_id="analysis_001",
            session_id="session_001",
            round_id="round_001",
            agent_id=agent_id,
            visible_clue_ids=("clue_001",),
            facts=("A fact",),
        )


def test_analysis_requires_fact_deduction_or_proposed_lead() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        AgentAnalysis(
            analysis_id="analysis_001",
            session_id="session_001",
            round_id="round_001",
            agent_id="sherlock",
            visible_clue_ids=("clue_001",),
            evidence=(make_evidence(),),
        )


@pytest.mark.parametrize("status", list(HypothesisStatus))
def test_active_and_discarded_hypotheses(status: HypothesisStatus) -> None:
    hypothesis = Hypothesis(
        hypothesis_id=f"hypothesis_{status.value}",
        session_id="session_001",
        round_id="round_001",
        statement="  The visitor entered through the window.  ",
        status=status,
    )

    assert hypothesis.status is status
    assert hypothesis.statement == "  The visitor entered through the window.  "


def test_hypothesis_accepts_every_evidence_relation() -> None:
    evidence = tuple(make_evidence(relation) for relation in EvidenceRelation)

    hypothesis = Hypothesis(
        hypothesis_id="hypothesis_001",
        session_id="session_001",
        round_id="round_001",
        statement="The visitor entered through the window.",
        status=HypothesisStatus.ACTIVE,
        evidence=evidence,
    )

    assert tuple(item.relation for item in hypothesis.evidence) == tuple(
        EvidenceRelation
    )


def test_hypothesis_revision_references_previous_record_by_id() -> None:
    revision = Hypothesis(
        hypothesis_id="hypothesis_002",
        session_id="session_001",
        round_id="round_001",
        statement="The visitor left through the window.",
        status=HypothesisStatus.ACTIVE,
        previous_hypothesis_id="hypothesis_001",
    )

    assert revision.previous_hypothesis_id == "hypothesis_001"


def test_hypothesis_cannot_reference_itself() -> None:
    with pytest.raises(ValidationError, match="itself"):
        Hypothesis(
            hypothesis_id="hypothesis_001",
            session_id="session_001",
            round_id="round_001",
            statement="A theory.",
            status=HypothesisStatus.ACTIVE,
            previous_hypothesis_id="hypothesis_001",
        )


@pytest.mark.parametrize("model", [Hypothesis, GroupDecision])
@pytest.mark.parametrize("field_name", ["session_id", "round_id"])
def test_round_owned_reasoning_records_require_ownership_fields(
    model: type[Hypothesis] | type[GroupDecision],
    field_name: str,
) -> None:
    if model is Hypothesis:
        payload: dict[str, object] = {
            **round_owned_context(),
            "hypothesis_id": "hypothesis_001",
            "statement": "A theory.",
            "status": "active",
        }
    else:
        payload = {
            **round_owned_context(),
            "decision_id": "decision_001",
            "decision_type": "pursue_lead",
            "summary": "Pursue it.",
        }
    del payload[field_name]

    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("model", [Hypothesis, GroupDecision])
@pytest.mark.parametrize("field_name", ["session_id", "round_id"])
def test_round_owned_reasoning_records_reject_empty_ownership(
    model: type[Hypothesis] | type[GroupDecision],
    field_name: str,
) -> None:
    payload: dict[str, object]
    if model is Hypothesis:
        payload = {
            **round_owned_context(),
            "hypothesis_id": "hypothesis_001",
            "statement": "A theory.",
            "status": "active",
        }
    else:
        payload = {
            **round_owned_context(),
            "decision_id": "decision_001",
            "decision_type": "pursue_lead",
            "summary": "Pursue it.",
        }
    payload[field_name] = "  "

    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_hypothesis_json_round_trip_preserves_ownership_and_evidence_order() -> None:
    hypothesis = Hypothesis(
        hypothesis_id="hypothesis_001",
        session_id="session_001",
        round_id="round_001",
        statement="A theory.",
        status=HypothesisStatus.ACTIVE,
        evidence=(
            EvidenceReference(clue_id="clue_002", relation="context"),
            EvidenceReference(clue_id="clue_001", relation="supports"),
        ),
    )

    restored = Hypothesis.model_validate_json(hypothesis.model_dump_json())

    assert restored == hypothesis
    assert restored.session_id == "session_001"
    assert restored.round_id == "round_001"
    assert tuple(item.clue_id for item in restored.evidence) == (
        "clue_002",
        "clue_001",
    )


@pytest.mark.parametrize("decision_type", list(GroupDecisionType))
def test_all_group_decision_types_are_supported(
    decision_type: GroupDecisionType,
) -> None:
    decision = GroupDecision(
        decision_id=f"decision_{decision_type.value}",
        session_id="session_001",
        round_id="round_001",
        decision_type=decision_type,
        summary="  The group explicitly adopted this action.  ",
    )

    assert decision.decision_type is decision_type
    assert decision.summary == "  The group explicitly adopted this action.  "


def test_group_decision_references_records_only_by_id() -> None:
    decision = GroupDecision(
        decision_id="decision_001",
        session_id="session_001",
        round_id="round_001",
        decision_type=GroupDecisionType.ADOPT_HYPOTHESIS,
        summary="Adopt the window hypothesis.",
        analysis_ids=("analysis_001",),
        hypothesis_ids=("hypothesis_001",),
        evidence=(make_evidence(),),
    )

    assert decision.analysis_ids == ("analysis_001",)
    assert decision.hypothesis_ids == ("hypothesis_001",)
    assert set(decision.model_dump()) == {
        "decision_id",
        "session_id",
        "round_id",
        "decision_type",
        "summary",
        "analysis_ids",
        "hypothesis_ids",
        "evidence",
    }


@pytest.mark.parametrize("field_name", ["facts", "deductions", "proposed_leads"])
def test_analysis_rejects_duplicate_text_entries(field_name: str) -> None:
    payload = {
        **analysis_context(),
        "analysis_id": "analysis_001",
        "agent_id": "sherlock",
        "facts": ["A fact"],
        field_name: ["Repeated", "Repeated"],
    }

    with pytest.raises(ValidationError, match="duplicates"):
        AgentAnalysis.model_validate(payload)


@pytest.mark.parametrize("field_name", ["analysis_ids", "hypothesis_ids"])
def test_group_decision_rejects_duplicate_ids(field_name: str) -> None:
    payload = {
        **round_owned_context(),
        "decision_id": "decision_001",
        "decision_type": "pursue_lead",
        "summary": "Pursue the lead.",
        field_name: ["record_001", "record_001"],
    }

    with pytest.raises(ValidationError, match="duplicates"):
        GroupDecision.model_validate(payload)


@pytest.mark.parametrize("model", [AgentAnalysis, Hypothesis, GroupDecision])
def test_reasoning_models_reject_duplicate_evidence_references(
    model: type[AgentAnalysis] | type[Hypothesis] | type[GroupDecision],
) -> None:
    evidence = [
        {"clue_id": "clue_001", "relation": "supports"},
        {"clue_id": "clue_001", "relation": "supports"},
    ]
    if model is AgentAnalysis:
        payload = {
            **analysis_context(),
            "analysis_id": "analysis_001",
            "agent_id": "sherlock",
            "facts": ["A fact"],
            "evidence": evidence,
        }
    elif model is Hypothesis:
        payload = {
            **round_owned_context(),
            "hypothesis_id": "hypothesis_001",
            "statement": "A theory.",
            "status": "active",
            "evidence": evidence,
        }
    else:
        payload = {
            **round_owned_context(),
            "decision_id": "decision_001",
            "decision_type": "pursue_lead",
            "summary": "Pursue it.",
            "evidence": evidence,
        }

    with pytest.raises(ValidationError, match="duplicate references"):
        model.model_validate(payload)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            Hypothesis,
            {
                **round_owned_context(),
                "hypothesis_id": "hypothesis_001",
                "statement": "A theory.",
                "status": "unknown",
            },
        ),
        (
            GroupDecision,
            {
                **round_owned_context(),
                "decision_id": "decision_001",
                "decision_type": "finish_investigation",
                "summary": "Finish.",
            },
        ),
    ],
)
def test_unsupported_reasoning_enum_values_are_rejected(
    model: type[Hypothesis] | type[GroupDecision],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("statement", ["", "  \t\n"])
def test_blank_hypothesis_statement_is_rejected(statement: str) -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            hypothesis_id="hypothesis_001",
            session_id="session_001",
            round_id="round_001",
            statement=statement,
            status=HypothesisStatus.ACTIVE,
        )


@pytest.mark.parametrize("summary", ["", "  \t\n"])
def test_blank_group_decision_summary_is_rejected(summary: str) -> None:
    with pytest.raises(ValidationError):
        GroupDecision(
            decision_id="decision_001",
            session_id="session_001",
            round_id="round_001",
            decision_type=GroupDecisionType.REQUEST_INFORMATION,
            summary=summary,
        )


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            AgentAnalysis,
            {
                **analysis_context(),
                "analysis_id": "analysis_001",
                "agent_id": "sherlock",
                "facts": ["A fact"],
                "confidence": 0.9,
            },
        ),
        (
            Hypothesis,
            {
                **round_owned_context(),
                "hypothesis_id": "hypothesis_001",
                "statement": "A theory.",
                "status": "active",
                "updated_at": "now",
            },
        ),
        (
            GroupDecision,
            {
                **round_owned_context(),
                "decision_id": "decision_001",
                "decision_type": "request_information",
                "summary": "Ask for details.",
                "consensus": True,
            },
        ),
    ],
)
def test_reasoning_models_forbid_extra_fields(
    model: type[AgentAnalysis] | type[Hypothesis] | type[GroupDecision],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_reasoning_models_are_frozen() -> None:
    analysis = AgentAnalysis(
        analysis_id="analysis_001",
        session_id="session_001",
        round_id="round_001",
        agent_id="sherlock",
        visible_clue_ids=("clue_001",),
        facts=("A fact",),
    )
    hypothesis = Hypothesis(
        hypothesis_id="hypothesis_001",
        session_id="session_001",
        round_id="round_001",
        statement="A theory.",
        status=HypothesisStatus.DISCARDED,
    )
    decision = GroupDecision(
        decision_id="decision_001",
        session_id="session_001",
        round_id="round_001",
        decision_type=GroupDecisionType.DISCARD_HYPOTHESIS,
        summary="Discard the theory.",
    )

    with pytest.raises(ValidationError):
        analysis.facts = ("Changed",)
    with pytest.raises(ValidationError):
        hypothesis.status = HypothesisStatus.ACTIVE
    with pytest.raises(ValidationError):
        decision.summary = "Changed"


def test_analysis_requires_temporal_context_fields() -> None:
    base = {
        **analysis_context(),
        "analysis_id": "analysis_001",
        "agent_id": "sherlock",
        "facts": ["A fact"],
    }

    for field_name in ("session_id", "round_id", "visible_clue_ids"):
        payload = dict(base)
        del payload[field_name]
        with pytest.raises(ValidationError):
            AgentAnalysis.model_validate(payload)


@pytest.mark.parametrize("field_name", ["session_id", "round_id"])
def test_analysis_rejects_empty_ownership_identifiers(field_name: str) -> None:
    payload = {
        **analysis_context(),
        "analysis_id": "analysis_001",
        "agent_id": "sherlock",
        "facts": ["A fact"],
        field_name: "  ",
    }

    with pytest.raises(ValidationError):
        AgentAnalysis.model_validate(payload)


def test_analysis_visibility_is_an_ordered_unique_tuple() -> None:
    analysis = AgentAnalysis.model_validate(
        {
            **analysis_context(),
            "analysis_id": "analysis_001",
            "agent_id": "sherlock",
            "visible_clue_ids": ["clue_002", "clue_001"],
            "facts": ["A fact"],
        }
    )

    assert analysis.visible_clue_ids == ("clue_002", "clue_001")
    with pytest.raises(ValidationError, match="duplicates"):
        AgentAnalysis.model_validate(
            {
                **analysis_context(),
                "analysis_id": "analysis_002",
                "agent_id": "sherlock",
                "visible_clue_ids": ["clue_001", "clue_001"],
                "facts": ["A fact"],
            }
        )


def test_analysis_json_round_trip_preserves_visibility_order() -> None:
    analysis = AgentAnalysis.model_validate(
        {
            **analysis_context(),
            "analysis_id": "analysis_001",
            "agent_id": "sherlock",
            "visible_clue_ids": ["clue_002", "clue_001"],
            "facts": ["A fact"],
        }
    )

    restored = AgentAnalysis.model_validate_json(analysis.model_dump_json())

    assert restored == analysis
    assert restored.visible_clue_ids == ("clue_002", "clue_001")


def test_list_inputs_become_ordered_tuples_and_json_round_trips() -> None:
    payload = {
        **round_owned_context(),
        "decision_id": "decision_001",
        "decision_type": "adopt_hypothesis",
        "summary": "Adopt the theory.",
        "analysis_ids": ["analysis_002", "analysis_001"],
        "hypothesis_ids": ["hypothesis_002", "hypothesis_001"],
        "evidence": [
            {"clue_id": "clue_002", "relation": "context"},
            {"clue_id": "clue_001", "relation": "contradicts"},
        ],
    }

    decision = GroupDecision.model_validate(payload)
    restored = GroupDecision.model_validate_json(decision.model_dump_json())

    assert decision.analysis_ids == ("analysis_002", "analysis_001")
    assert decision.hypothesis_ids == ("hypothesis_002", "hypothesis_001")
    assert tuple(item.clue_id for item in decision.evidence) == (
        "clue_002",
        "clue_001",
    )
    assert tuple(item.relation for item in decision.evidence) == (
        EvidenceRelation.CONTEXT,
        EvidenceRelation.CONTRADICTS,
    )
    assert restored == decision


def make_round(**updates: object) -> InvestigationRound:
    payload: dict[str, object] = {
        "session_id": "session_001",
        "round_id": "session_001_round_0001",
        "round_index": 1,
        "revealed_clue_id": "session_001_clue_0001",
        "visible_clue_ids": ["session_001_clue_0001"],
        "status": "awaiting_analyses",
    }
    payload.update(updates)
    return InvestigationRound.model_validate(payload)


def test_minimal_investigation_round_uses_structural_defaults() -> None:
    investigation_round = make_round()

    assert investigation_round.round_index == 1
    assert investigation_round.analysis_ids == ()
    assert investigation_round.discussion_run is None
    assert investigation_round.decision_id is None
    assert (
        investigation_round.status
        is InvestigationRoundStatus.AWAITING_ANALYSES
    )


@pytest.mark.parametrize("status", list(InvestigationRoundStatus))
def test_investigation_round_accepts_every_status(
    status: InvestigationRoundStatus,
) -> None:
    assert make_round(status=status).status is status


def test_investigation_round_converts_lists_to_ordered_tuples() -> None:
    investigation_round = make_round(
        visible_clue_ids=["clue_002", "clue_001"],
        analysis_ids=["analysis_002", "analysis_001"],
    )

    assert investigation_round.visible_clue_ids == ("clue_002", "clue_001")
    assert investigation_round.analysis_ids == ("analysis_002", "analysis_001")


@pytest.mark.parametrize(
    "updates",
    [
        {"session_id": ""},
        {"round_id": "   "},
        {"revealed_clue_id": ""},
        {"visible_clue_ids": ["clue_001", " "]},
        {"analysis_ids": [""]},
        {"decision_id": "  "},
    ],
)
def test_investigation_round_rejects_empty_identifiers(
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        make_round(**updates)


@pytest.mark.parametrize("round_index", [0, -1, True, False, 1.0])
def test_investigation_round_rejects_invalid_indexes(
    round_index: object,
) -> None:
    with pytest.raises(ValidationError):
        make_round(round_index=round_index)


def test_investigation_round_rejects_unsupported_status_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        make_round(status="failed")
    with pytest.raises(ValidationError):
        make_round(retry_count=1)


def test_investigation_round_is_frozen() -> None:
    investigation_round = make_round()

    with pytest.raises(ValidationError):
        investigation_round.status = InvestigationRoundStatus.COMPLETED


def test_investigation_round_json_round_trip_preserves_tuple_order() -> None:
    investigation_round = make_round(
        visible_clue_ids=["clue_001", "clue_002"],
        analysis_ids=["analysis_sherlock", "analysis_poirot"],
    )

    restored = InvestigationRound.model_validate_json(
        investigation_round.model_dump_json()
    )

    assert restored == investigation_round
    assert restored.visible_clue_ids == ("clue_001", "clue_002")
    assert restored.analysis_ids == ("analysis_sherlock", "analysis_poirot")


def test_investigation_round_accepts_existing_conversation_run() -> None:
    discussion_run = ConversationRun(
        run_id="session_001_round_0001_discussion",
        topic="Discuss the first clue.",
        character_ids=("sherlock", "poirot"),
        turn_count=1,
        seed=42,
        provider="mock",
        model="mock-round-robin",
        created_at=datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc),
        status="running",
    )

    investigation_round = make_round(discussion_run=discussion_run)
    restored = InvestigationRound.model_validate_json(
        investigation_round.model_dump_json()
    )

    assert investigation_round.discussion_run is discussion_run
    assert restored.discussion_run == discussion_run
