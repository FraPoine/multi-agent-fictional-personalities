"""Tests for the immutable investigation session aggregate."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models import (
    FinalTheory,
    InvestigationRound,
    InvestigationSession,
    InvestigationStatus,
)


def minimal_payload(status: str = "setup") -> dict[str, object]:
    return {
        "session_id": "session_001",
        "case_introduction": "  A visitor vanished from a locked room.  ",
        "participant_ids": ["sherlock", "poirot"],
        "status": status,
    }


def complete_payload() -> dict[str, object]:
    return {
        **minimal_payload("completed"),
        "clues": [
            {"clue_id": "clue_001", "text": "The window is open.", "reveal_order": 0},
            {"clue_id": "clue_002", "text": "Mud lies outside.", "reveal_order": 1},
        ],
        "analyses": [
            {
                "analysis_id": "analysis_001",
                "agent_id": "sherlock",
                "facts": ["The window is open."],
                "deductions": ["Someone may have used the window."],
                "evidence": [{"clue_id": "clue_001", "relation": "supports"}],
                "proposed_leads": ["Inspect the garden."],
            }
        ],
        "hypotheses": [
            {
                "hypothesis_id": "hypothesis_001",
                "statement": "The visitor used the window.",
                "status": "discarded",
                "evidence": [{"clue_id": "clue_001", "relation": "context"}],
            },
            {
                "hypothesis_id": "hypothesis_002",
                "statement": "An accomplice waited outside.",
                "status": "active",
                "evidence": [{"clue_id": "clue_002", "relation": "supports"}],
                "previous_hypothesis_id": "hypothesis_001",
            },
        ],
        "decisions": [
            {
                "decision_id": "decision_001",
                "decision_type": "adopt_hypothesis",
                "summary": "Adopt the accomplice hypothesis.",
                "analysis_ids": ["analysis_001"],
                "hypothesis_ids": ["hypothesis_002"],
                "evidence": [{"clue_id": "clue_002", "relation": "supports"}],
            }
        ],
        "final_theory": {
            "final_theory_id": "final_001",
            "summary": "The visitor escaped with an accomplice.",
            "hypothesis_ids": ["hypothesis_002"],
            "evidence": [
                {"clue_id": "clue_001", "relation": "context"},
                {"clue_id": "clue_002", "relation": "supports"},
            ],
        },
    }


def round_payload(
    round_index: int = 1,
    *,
    round_id: str | None = None,
    session_id: str = "session_001",
) -> dict[str, object]:
    return {
        "session_id": session_id,
        "round_id": round_id or f"session_001_round_{round_index:04d}",
        "round_index": round_index,
        "revealed_clue_id": f"session_001_clue_{round_index:04d}",
        "visible_clue_ids": [
            f"session_001_clue_{index:04d}"
            for index in range(1, round_index + 1)
        ],
        "status": "awaiting_analyses",
    }


def test_minimal_setup_session_is_valid_and_preserves_introduction() -> None:
    session = InvestigationSession.model_validate(minimal_payload())

    assert session.status is InvestigationStatus.SETUP
    assert session.participant_ids == ("sherlock", "poirot")
    assert session.case_introduction == "  A visitor vanished from a locked room.  "
    assert session.clues == ()
    assert session.rounds == ()
    assert session.final_theory is None


def test_legacy_payload_without_rounds_deserializes_with_empty_tuple() -> None:
    payload = minimal_payload()

    from_dict = InvestigationSession.model_validate(payload)
    from_json = InvestigationSession.model_validate_json(
        '{"session_id":"session_001",'
        '"case_introduction":"A case.",'
        '"participant_ids":["sherlock","poirot"],'
        '"status":"setup"}'
    )

    assert "rounds" not in payload
    assert from_dict.rounds == ()
    assert from_json.rounds == ()


def test_session_accepts_one_round() -> None:
    session = InvestigationSession.model_validate(
        {**minimal_payload("active"), "rounds": [round_payload()]}
    )

    assert len(session.rounds) == 1
    assert isinstance(session.rounds[0], InvestigationRound)
    assert session.rounds[0].round_index == 1


def test_session_accepts_multiple_contiguous_rounds_in_order() -> None:
    session = InvestigationSession.model_validate(
        {
            **minimal_payload("active"),
            "rounds": [round_payload(1), round_payload(2), round_payload(3)],
        }
    )

    assert tuple(item.round_index for item in session.rounds) == (1, 2, 3)


def test_session_rejects_duplicate_round_ids() -> None:
    payload = {
        **minimal_payload("active"),
        "rounds": [
            round_payload(1, round_id="same"),
            round_payload(2, round_id="same"),
        ],
    }

    with pytest.raises(ValidationError, match="round_id"):
        InvestigationSession.model_validate(payload)


@pytest.mark.parametrize("indexes", [[1, 1], [2], [1, 3], [2, 1]])
def test_session_rejects_invalid_round_index_sequences(
    indexes: list[int],
) -> None:
    payload = {
        **minimal_payload("active"),
        "rounds": [
            round_payload(index, round_id=f"round_{position}")
            for position, index in enumerate(indexes)
        ],
    }

    with pytest.raises(ValidationError, match="round_index"):
        InvestigationSession.model_validate(payload)


def test_session_rejects_round_owned_by_another_session() -> None:
    payload = {
        **minimal_payload("active"),
        "rounds": [round_payload(session_id="session_002")],
    }

    with pytest.raises(ValidationError, match="belong"):
        InvestigationSession.model_validate(payload)


def test_session_round_json_round_trip_preserves_order() -> None:
    session = InvestigationSession.model_validate(
        {
            **minimal_payload("active"),
            "rounds": [round_payload(1), round_payload(2)],
        }
    )

    restored = InvestigationSession.model_validate_json(session.model_dump_json())

    assert restored == session
    assert tuple(item.round_id for item in restored.rounds) == (
        "session_001_round_0001",
        "session_001_round_0002",
    )


@pytest.mark.parametrize("status", ["active", "ready_for_final", "abandoned"])
def test_partial_statuses_accept_empty_sessions_without_final_theory(
    status: str,
) -> None:
    session = InvestigationSession.model_validate(minimal_payload(status))

    assert session.status.value == status
    assert session.final_theory is None


def test_complete_session_validates_full_graph() -> None:
    session = InvestigationSession.model_validate(complete_payload())

    assert session.status is InvestigationStatus.COMPLETED
    assert len(session.clues) == 2
    assert len(session.analyses) == 1
    assert len(session.hypotheses) == 2
    assert len(session.decisions) == 1
    assert session.final_theory is not None


@pytest.mark.parametrize("participant_ids", [[], ["sherlock"]])
def test_at_least_two_participants_are_required(
    participant_ids: list[str],
) -> None:
    payload = minimal_payload()
    payload["participant_ids"] = participant_ids

    with pytest.raises(ValidationError):
        InvestigationSession.model_validate(payload)


def test_duplicate_participants_are_rejected() -> None:
    payload = minimal_payload()
    payload["participant_ids"] = ["sherlock", "sherlock"]

    with pytest.raises(ValidationError, match="duplicates"):
        InvestigationSession.model_validate(payload)


@pytest.mark.parametrize(
    ("collection", "id_field", "entry"),
    [
        ("clues", "clue_id", {"clue_id": "same", "text": "A", "reveal_order": 0}),
        (
            "analyses",
            "analysis_id",
            {"analysis_id": "same", "agent_id": "sherlock", "facts": ["A"]},
        ),
        (
            "hypotheses",
            "hypothesis_id",
            {"hypothesis_id": "same", "statement": "A", "status": "active"},
        ),
        (
            "decisions",
            "decision_id",
            {"decision_id": "same", "decision_type": "pursue_lead", "summary": "A"},
        ),
    ],
)
def test_duplicate_collection_ids_are_rejected(
    collection: str,
    id_field: str,
    entry: dict[str, object],
) -> None:
    payload = minimal_payload()
    second = deepcopy(entry)
    if collection == "clues":
        second["reveal_order"] = 1
    payload[collection] = [entry, second]

    with pytest.raises(ValidationError, match=id_field):
        InvestigationSession.model_validate(payload)


def test_contiguous_clue_order_from_zero_is_valid() -> None:
    payload = minimal_payload("active")
    payload["clues"] = [
        {"clue_id": "clue_001", "text": "First", "reveal_order": 0},
        {"clue_id": "clue_002", "text": "Second", "reveal_order": 1},
    ]

    session = InvestigationSession.model_validate(payload)

    assert tuple(clue.reveal_order for clue in session.clues) == (0, 1)


@pytest.mark.parametrize("orders", [[1], [0, 2], [0, 0], [1, 0]])
def test_invalid_clue_order_is_rejected(orders: list[int]) -> None:
    payload = minimal_payload()
    payload["clues"] = [
        {"clue_id": f"clue_{index}", "text": "Revealed", "reveal_order": order}
        for index, order in enumerate(orders)
    ]

    with pytest.raises(ValidationError, match="reveal_order"):
        InvestigationSession.model_validate(payload)


def test_analysis_must_belong_to_participant() -> None:
    payload = minimal_payload()
    payload["analyses"] = [
        {"analysis_id": "analysis_001", "agent_id": "outsider", "facts": ["A"]}
    ]

    with pytest.raises(ValidationError, match="participants"):
        InvestigationSession.model_validate(payload)


@pytest.mark.parametrize("entity", ["analyses", "hypotheses", "decisions", "final_theory"])
def test_unknown_clue_reference_is_rejected_for_every_entity(entity: str) -> None:
    payload = minimal_payload("active")
    evidence = [{"clue_id": "missing", "relation": "context"}]
    if entity == "analyses":
        payload[entity] = [
            {
                "analysis_id": "analysis_001",
                "agent_id": "sherlock",
                "facts": ["A"],
                "evidence": evidence,
            }
        ]
    elif entity == "hypotheses":
        payload[entity] = [
            {"hypothesis_id": "hypothesis_001", "statement": "A", "status": "active", "evidence": evidence}
        ]
    elif entity == "decisions":
        payload[entity] = [
            {"decision_id": "decision_001", "decision_type": "pursue_lead", "summary": "A", "evidence": evidence}
        ]
    else:
        payload[entity] = {"final_theory_id": "final_001", "summary": "A", "evidence": evidence}

    with pytest.raises(ValidationError, match="session clues"):
        InvestigationSession.model_validate(payload)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("analysis_ids", "missing_analysis", "unknown analysis"),
        ("hypothesis_ids", "missing_hypothesis", "unknown hypothesis"),
    ],
)
def test_decision_references_must_resolve(
    field_name: str,
    value: str,
    message: str,
) -> None:
    payload = minimal_payload("active")
    payload["decisions"] = [
        {
            "decision_id": "decision_001",
            "decision_type": "pursue_lead",
            "summary": "A decision.",
            field_name: [value],
        }
    ]

    with pytest.raises(ValidationError, match=message):
        InvestigationSession.model_validate(payload)


def test_unknown_previous_hypothesis_is_rejected() -> None:
    payload = minimal_payload("active")
    payload["hypotheses"] = [
        {
            "hypothesis_id": "hypothesis_002",
            "statement": "A revision.",
            "status": "active",
            "previous_hypothesis_id": "missing",
        }
    ]

    with pytest.raises(ValidationError, match="must exist"):
        InvestigationSession.model_validate(payload)


def test_forward_hypothesis_revision_reference_is_rejected() -> None:
    payload = minimal_payload("active")
    payload["hypotheses"] = [
        {
            "hypothesis_id": "hypothesis_002",
            "statement": "Revision first.",
            "status": "active",
            "previous_hypothesis_id": "hypothesis_001",
        },
        {"hypothesis_id": "hypothesis_001", "statement": "Original.", "status": "discarded"},
    ]

    with pytest.raises(ValidationError, match="earlier"):
        InvestigationSession.model_validate(payload)


def test_final_theory_hypotheses_must_resolve() -> None:
    payload = minimal_payload("ready_for_final")
    payload["final_theory"] = {
        "final_theory_id": "final_001",
        "summary": "A conclusion.",
        "hypothesis_ids": ["missing"],
    }

    with pytest.raises(ValidationError, match="final theory"):
        InvestigationSession.model_validate(payload)


def test_completed_session_requires_final_theory() -> None:
    with pytest.raises(ValidationError, match="require a final theory"):
        InvestigationSession.model_validate(minimal_payload("completed"))


def test_list_inputs_become_ordered_tuples() -> None:
    session = InvestigationSession.model_validate(complete_payload())

    assert isinstance(session.participant_ids, tuple)
    assert isinstance(session.clues, tuple)
    assert isinstance(session.analyses, tuple)
    assert isinstance(session.hypotheses, tuple)
    assert isinstance(session.decisions, tuple)
    assert session.hypotheses[1].previous_hypothesis_id == "hypothesis_001"


def test_session_and_final_theory_are_frozen_and_forbid_extra_fields() -> None:
    session = InvestigationSession.model_validate(minimal_payload())
    theory = FinalTheory(final_theory_id="final_001", summary="A conclusion.")

    with pytest.raises(ValidationError):
        session.status = InvestigationStatus.ACTIVE
    with pytest.raises(ValidationError):
        theory.summary = "Changed"
    with pytest.raises(ValidationError):
        InvestigationSession.model_validate({**minimal_payload(), "clock": "now"})
    with pytest.raises(ValidationError):
        FinalTheory.model_validate(
            {"final_theory_id": "final_001", "summary": "A", "clue": {}}
        )


def test_final_theory_rejects_blank_summary_and_duplicate_references() -> None:
    with pytest.raises(ValidationError):
        FinalTheory(final_theory_id="final_001", summary="  ")
    with pytest.raises(ValidationError, match="duplicates"):
        FinalTheory(
            final_theory_id="final_001",
            summary="A",
            hypothesis_ids=("hypothesis_001", "hypothesis_001"),
        )
    with pytest.raises(ValidationError, match="duplicate references"):
        FinalTheory.model_validate(
            {
                "final_theory_id": "final_001",
                "summary": "A",
                "evidence": [
                    {"clue_id": "clue_001", "relation": "supports"},
                    {"clue_id": "clue_001", "relation": "supports"},
                ],
            }
        )


def test_complete_json_round_trip_and_serialization_are_deterministic() -> None:
    session = InvestigationSession.model_validate(complete_payload())

    first = session.model_dump_json()
    second = session.model_dump_json()
    restored = InvestigationSession.model_validate_json(first)

    assert first == second
    assert restored == session
    assert restored.model_dump_json() == first
    assert restored.status is InvestigationStatus.COMPLETED
    assert tuple(clue.clue_id for clue in restored.clues) == ("clue_001", "clue_002")
    assert tuple(item.hypothesis_id for item in restored.hypotheses) == (
        "hypothesis_001",
        "hypothesis_002",
    )
