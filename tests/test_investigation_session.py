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
        "rounds": [
            {
                "session_id": "session_001",
                "round_id": "round_001",
                "round_index": 1,
                "revealed_clue_id": "clue_001",
                "visible_clue_ids": ["clue_001"],
                "analysis_ids": ["analysis_001"],
                "decision_id": "decision_001",
                "status": "completed",
            },
            {
                "session_id": "session_001",
                "round_id": "round_002",
                "round_index": 2,
                "revealed_clue_id": "clue_002",
                "visible_clue_ids": ["clue_001", "clue_002"],
                "analysis_ids": ["analysis_002"],
                "decision_id": "decision_002",
                "status": "completed",
            }
        ],
        "analyses": [
            {
                "analysis_id": "analysis_001",
                "session_id": "session_001",
                "round_id": "round_001",
                "agent_id": "sherlock",
                "visible_clue_ids": ["clue_001"],
                "facts": ["The window is open."],
                "deductions": ["Someone may have used the window."],
                "evidence": [{"clue_id": "clue_001", "relation": "supports"}],
                "proposed_leads": ["Inspect the garden."],
            },
            {
                "analysis_id": "analysis_002",
                "session_id": "session_001",
                "round_id": "round_002",
                "agent_id": "sherlock",
                "visible_clue_ids": ["clue_001", "clue_002"],
                "facts": ["Mud lies outside."],
            }
        ],
        "hypotheses": [
            {
                "hypothesis_id": "hypothesis_001",
                "session_id": "session_001",
                "round_id": "round_001",
                "statement": "The visitor used the window.",
                "status": "discarded",
                "evidence": [{"clue_id": "clue_001", "relation": "context"}],
            },
            {
                "hypothesis_id": "hypothesis_002",
                "session_id": "session_001",
                "round_id": "round_002",
                "statement": "An accomplice waited outside.",
                "status": "active",
                "evidence": [{"clue_id": "clue_002", "relation": "supports"}],
                "previous_hypothesis_id": "hypothesis_001",
            },
        ],
        "decisions": [
            {
                "decision_id": "decision_001",
                "session_id": "session_001",
                "round_id": "round_001",
                "decision_type": "adopt_hypothesis",
                "summary": "Adopt the accomplice hypothesis.",
                "analysis_ids": ["analysis_001"],
                "hypothesis_ids": ["hypothesis_001"],
                "evidence": [{"clue_id": "clue_001", "relation": "supports"}],
            },
            {
                "decision_id": "decision_002",
                "session_id": "session_001",
                "round_id": "round_002",
                "decision_type": "adopt_hypothesis",
                "summary": "Adopt the accomplice hypothesis.",
                "analysis_ids": ["analysis_002"],
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


def clue_payloads(count: int) -> list[dict[str, object]]:
    return [
        {
            "clue_id": f"session_001_clue_{index:04d}",
            "text": f"Clue {index}.",
            "reveal_order": index - 1,
        }
        for index in range(1, count + 1)
    ]


def round_payload_for_analysis(
    round_index: int = 1,
    *,
    analysis_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "session_id": "session_001",
        "round_id": f"round_{round_index:03d}",
        "round_index": round_index,
        "revealed_clue_id": f"clue_{round_index:03d}",
        "visible_clue_ids": [
            f"clue_{index:03d}" for index in range(1, round_index + 1)
        ],
        "analysis_ids": [] if analysis_ids is None else analysis_ids,
        "status": "awaiting_analyses",
    }


def analysis_payload(
    analysis_id: str = "analysis_001",
    *,
    round_index: int = 1,
    agent_id: str = "sherlock",
) -> dict[str, object]:
    return {
        "analysis_id": analysis_id,
        "session_id": "session_001",
        "round_id": f"round_{round_index:03d}",
        "agent_id": agent_id,
        "visible_clue_ids": [
            f"clue_{index:03d}" for index in range(1, round_index + 1)
        ],
        "facts": ["A fact."],
    }


def hypothesis_payload(
    hypothesis_id: str = "hypothesis_001",
    *,
    round_index: int = 1,
    previous_hypothesis_id: str | None = None,
) -> dict[str, object]:
    return {
        "hypothesis_id": hypothesis_id,
        "session_id": "session_001",
        "round_id": f"round_{round_index:03d}",
        "statement": f"Theory {hypothesis_id}.",
        "status": "active",
        "previous_hypothesis_id": previous_hypothesis_id,
    }


def decision_payload(
    decision_id: str = "decision_001",
    *,
    round_index: int = 1,
    analysis_ids: list[str] | None = None,
    hypothesis_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "session_id": "session_001",
        "round_id": f"round_{round_index:03d}",
        "decision_type": "pursue_lead",
        "summary": f"Decision {decision_id}.",
        "analysis_ids": [] if analysis_ids is None else analysis_ids,
        "hypothesis_ids": [] if hypothesis_ids is None else hypothesis_ids,
    }


def analysis_session_payload(*, two_rounds: bool = False) -> dict[str, object]:
    round_count = 2 if two_rounds else 1
    return {
        **minimal_payload("active"),
        "clues": [
            {
                "clue_id": f"clue_{index:03d}",
                "text": f"Clue {index}.",
                "reveal_order": index - 1,
            }
            for index in range(1, round_count + 1)
        ],
        "rounds": [
            round_payload_for_analysis(index)
            for index in range(1, round_count + 1)
        ],
    }


def completed_decision_session_payload(
    *,
    two_rounds: bool = False,
) -> dict[str, object]:
    payload = analysis_session_payload(two_rounds=two_rounds)
    round_count = 2 if two_rounds else 1
    payload["analyses"] = [
        analysis_payload(f"analysis_{index:03d}", round_index=index)
        for index in range(1, round_count + 1)
    ]
    payload["decisions"] = [
        decision_payload(
            f"decision_{index:03d}",
            round_index=index,
            analysis_ids=[f"analysis_{index:03d}"],
        )
        for index in range(1, round_count + 1)
    ]
    for index in range(round_count):
        payload["rounds"][index]["analysis_ids"] = [
            f"analysis_{index + 1:03d}"
        ]
        payload["rounds"][index]["decision_id"] = (
            f"decision_{index + 1:03d}"
        )
        payload["rounds"][index]["status"] = "completed"
    return payload


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
        {
            **minimal_payload("active"),
            "clues": clue_payloads(1),
            "rounds": [round_payload()],
        }
    )

    assert len(session.rounds) == 1
    assert isinstance(session.rounds[0], InvestigationRound)
    assert session.rounds[0].round_index == 1


def test_session_accepts_multiple_contiguous_rounds_in_order() -> None:
    session = InvestigationSession.model_validate(
        {
            **minimal_payload("active"),
            "clues": clue_payloads(3),
            "rounds": [round_payload(1), round_payload(2), round_payload(3)],
        }
    )

    assert tuple(item.round_index for item in session.rounds) == (1, 2, 3)


def test_session_rejects_duplicate_round_ids() -> None:
    payload = {
        **minimal_payload("active"),
        "clues": clue_payloads(2),
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
        "clues": clue_payloads(max(len(indexes), max(indexes))),
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
        "clues": clue_payloads(1),
        "rounds": [round_payload(session_id="session_002")],
    }

    with pytest.raises(ValidationError, match="belong"):
        InvestigationSession.model_validate(payload)


def test_session_round_json_round_trip_preserves_order() -> None:
    session = InvestigationSession.model_validate(
        {
            **minimal_payload("active"),
            "clues": clue_payloads(2),
            "rounds": [round_payload(1), round_payload(2)],
        }
    )

    restored = InvestigationSession.model_validate_json(session.model_dump_json())

    assert restored == session
    assert tuple(item.round_id for item in restored.rounds) == (
        "session_001_round_0001",
        "session_001_round_0002",
    )


def test_legacy_snapshot_may_have_clues_without_rounds() -> None:
    session = InvestigationSession.model_validate(
        {**minimal_payload("active"), "clues": clue_payloads(2)}
    )

    assert len(session.clues) == 2
    assert session.rounds == ()


def test_session_rejects_more_rounds_than_clues() -> None:
    payload = {
        **minimal_payload("active"),
        "clues": clue_payloads(1),
        "rounds": [round_payload(1), round_payload(2)],
    }

    with pytest.raises(ValidationError, match="more rounds than clues"):
        InvestigationSession.model_validate(payload)


def test_session_rejects_wrong_revealed_clue_for_round_position() -> None:
    second_round = round_payload(2)
    second_round["revealed_clue_id"] = "session_001_clue_0001"
    payload = {
        **minimal_payload("active"),
        "clues": clue_payloads(2),
        "rounds": [round_payload(1), second_round],
    }

    with pytest.raises(ValidationError, match="revealed_clue_id"):
        InvestigationSession.model_validate(payload)


@pytest.mark.parametrize(
    "visible_ids",
    [
        [],
        ["session_001_clue_0002"],
        ["session_001_clue_0002", "session_001_clue_0001"],
        ["session_001_clue_0001", "unknown_clue"],
    ],
)
def test_session_rejects_non_historical_round_visibility(
    visible_ids: list[str],
) -> None:
    first_round = round_payload(1)
    first_round["visible_clue_ids"] = visible_ids
    payload = {
        **minimal_payload("active"),
        "clues": clue_payloads(2),
        "rounds": [first_round],
    }

    with pytest.raises(ValidationError, match="round history visibility"):
        InvestigationSession.model_validate(payload)


def test_coordinated_future_clue_forgery_is_rejected_by_round_history() -> None:
    first_round = round_payload_for_analysis(1, analysis_ids=["analysis_001"])
    first_round["visible_clue_ids"] = ["clue_001", "clue_002"]
    analysis = analysis_payload(round_index=1)
    analysis["visible_clue_ids"] = ["clue_001", "clue_002"]
    analysis["evidence"] = [{"clue_id": "clue_002", "relation": "supports"}]
    payload = analysis_session_payload(two_rounds=True)
    payload["rounds"] = [first_round]
    payload["analyses"] = [analysis]

    with pytest.raises(ValidationError, match="round history visibility"):
        InvestigationSession.model_validate(payload)


def test_valid_analysis_matches_session_round_and_visibility() -> None:
    payload = analysis_session_payload()
    payload["analyses"] = [analysis_payload()]
    payload["rounds"][0]["analysis_ids"] = ["analysis_001"]

    session = InvestigationSession.model_validate(payload)

    assert session.analyses[0].session_id == session.session_id
    assert session.analyses[0].round_id == session.rounds[0].round_id
    assert session.analyses[0].visible_clue_ids == ("clue_001",)


def test_analysis_from_another_session_is_rejected() -> None:
    payload = analysis_session_payload()
    analysis = analysis_payload()
    analysis["session_id"] = "session_002"
    payload["analyses"] = [analysis]
    payload["rounds"][0]["analysis_ids"] = ["analysis_001"]

    with pytest.raises(ValidationError, match="analysis_001.*another session"):
        InvestigationSession.model_validate(payload)


def test_analysis_referencing_unknown_round_is_rejected() -> None:
    payload = analysis_session_payload()
    analysis = analysis_payload()
    analysis["round_id"] = "round_missing"
    payload["analyses"] = [analysis]

    with pytest.raises(ValidationError, match="analysis_001.*unknown round"):
        InvestigationSession.model_validate(payload)


@pytest.mark.parametrize(
    "visible_clue_ids",
    [
        ["clue_001"],
        ["clue_002", "clue_001"],
        ["clue_001", "clue_002", "clue_003"],
        [],
    ],
)
def test_analysis_visibility_must_exactly_match_round_snapshot(
    visible_clue_ids: list[str],
) -> None:
    payload = analysis_session_payload(two_rounds=True)
    analysis = analysis_payload(round_index=2)
    analysis["visible_clue_ids"] = visible_clue_ids
    payload["analyses"] = [analysis]
    payload["rounds"][1]["analysis_ids"] = ["analysis_001"]

    with pytest.raises(ValidationError, match="visibility snapshot.*exactly"):
        InvestigationSession.model_validate(payload)


def test_analysis_referencing_unknown_clue_is_rejected() -> None:
    payload = analysis_session_payload()
    analysis = analysis_payload()
    analysis["evidence"] = [{"clue_id": "missing", "relation": "context"}]
    payload["analyses"] = [analysis]
    payload["rounds"][0]["analysis_ids"] = ["analysis_001"]

    with pytest.raises(ValidationError, match="analysis_001.*unknown clue"):
        InvestigationSession.model_validate(payload)


def test_round_one_analysis_cannot_reference_clue_revealed_in_round_two() -> None:
    payload = analysis_session_payload(two_rounds=True)
    analysis = analysis_payload(round_index=1)
    analysis["evidence"] = [{"clue_id": "clue_002", "relation": "supports"}]
    payload["analyses"] = [analysis]
    payload["rounds"][0]["analysis_ids"] = ["analysis_001"]

    with pytest.raises(ValidationError, match="outside its visibility snapshot"):
        InvestigationSession.model_validate(payload)


def test_same_agent_cannot_have_two_analyses_in_one_round() -> None:
    payload = analysis_session_payload()
    payload["analyses"] = [
        analysis_payload("analysis_001"),
        analysis_payload("analysis_002"),
    ]
    payload["rounds"][0]["analysis_ids"] = ["analysis_001", "analysis_002"]

    with pytest.raises(ValidationError, match="at most one analysis per round"):
        InvestigationSession.model_validate(payload)


def test_same_agent_can_have_one_analysis_in_each_round() -> None:
    payload = analysis_session_payload(two_rounds=True)
    payload["analyses"] = [
        analysis_payload("analysis_001", round_index=1),
        analysis_payload("analysis_002", round_index=2),
    ]
    payload["rounds"][0]["analysis_ids"] = ["analysis_001"]
    payload["rounds"][1]["analysis_ids"] = ["analysis_002"]

    session = InvestigationSession.model_validate(payload)

    assert tuple(item.round_id for item in session.analyses) == (
        "round_001",
        "round_002",
    )


def test_participants_in_same_round_share_exact_visibility_snapshot() -> None:
    payload = analysis_session_payload()
    payload["analyses"] = [
        analysis_payload("analysis_sherlock", agent_id="sherlock"),
        analysis_payload("analysis_poirot", agent_id="poirot"),
    ]
    payload["rounds"][0]["analysis_ids"] = [
        "analysis_sherlock",
        "analysis_poirot",
    ]

    session = InvestigationSession.model_validate(payload)

    assert {item.visible_clue_ids for item in session.analyses} == {
        ("clue_001",)
    }


def test_round_rejects_unknown_analysis_id() -> None:
    payload = analysis_session_payload()
    payload["rounds"][0]["analysis_ids"] = ["missing"]

    with pytest.raises(ValidationError, match="unknown analysis"):
        InvestigationSession.model_validate(payload)


def test_round_rejects_analysis_belonging_to_another_round() -> None:
    payload = analysis_session_payload(two_rounds=True)
    payload["analyses"] = [analysis_payload(round_index=1)]
    payload["rounds"][1]["analysis_ids"] = ["analysis_001"]

    with pytest.raises(ValidationError, match="another round"):
        InvestigationSession.model_validate(payload)


def test_round_rejects_omitted_analysis() -> None:
    payload = analysis_session_payload()
    payload["analyses"] = [analysis_payload()]

    with pytest.raises(ValidationError, match="match session analysis order"):
        InvestigationSession.model_validate(payload)


def test_round_rejects_duplicate_analysis_ids() -> None:
    payload = analysis_session_payload()
    payload["rounds"][0]["analysis_ids"] = ["analysis_001", "analysis_001"]

    with pytest.raises(ValidationError, match="duplicates"):
        InvestigationSession.model_validate(payload)


def test_round_analysis_ids_must_follow_session_analysis_order() -> None:
    payload = analysis_session_payload()
    payload["analyses"] = [
        analysis_payload("analysis_sherlock", agent_id="sherlock"),
        analysis_payload("analysis_poirot", agent_id="poirot"),
    ]
    payload["rounds"][0]["analysis_ids"] = [
        "analysis_poirot",
        "analysis_sherlock",
    ]

    with pytest.raises(ValidationError, match="match session analysis order"):
        InvestigationSession.model_validate(payload)


def test_two_round_analysis_context_json_round_trip_is_deterministic() -> None:
    payload = analysis_session_payload(two_rounds=True)
    payload["analyses"] = [
        analysis_payload("analysis_001", round_index=1),
        analysis_payload("analysis_002", round_index=2),
    ]
    payload["rounds"][0]["analysis_ids"] = ["analysis_001"]
    payload["rounds"][1]["analysis_ids"] = ["analysis_002"]
    session = InvestigationSession.model_validate(payload)

    first = session.model_dump_json()
    restored = InvestigationSession.model_validate_json(first)

    assert restored == session
    assert restored.model_dump_json() == first
    assert restored.analyses[0].visible_clue_ids == ("clue_001",)
    assert restored.analyses[1].visible_clue_ids == (
        "clue_001",
        "clue_002",
    )


def test_hypothesis_belongs_to_its_session_and_round() -> None:
    payload = analysis_session_payload()
    payload["hypotheses"] = [hypothesis_payload()]

    session = InvestigationSession.model_validate(payload)

    assert session.hypotheses[0].session_id == "session_001"
    assert session.hypotheses[0].round_id == "round_001"


def test_hypothesis_from_another_session_is_rejected() -> None:
    payload = analysis_session_payload()
    hypothesis = hypothesis_payload()
    hypothesis["session_id"] = "session_002"
    payload["hypotheses"] = [hypothesis]

    with pytest.raises(ValidationError, match="hypothesis_001.*another session"):
        InvestigationSession.model_validate(payload)


def test_hypothesis_referencing_unknown_round_is_rejected() -> None:
    payload = analysis_session_payload()
    hypothesis = hypothesis_payload()
    hypothesis["round_id"] = "round_missing"
    payload["hypotheses"] = [hypothesis]

    with pytest.raises(ValidationError, match="hypothesis_001.*unknown round"):
        InvestigationSession.model_validate(payload)


def test_hypothesis_may_use_clue_visible_in_its_round() -> None:
    payload = analysis_session_payload()
    hypothesis = hypothesis_payload()
    hypothesis["evidence"] = [{"clue_id": "clue_001", "relation": "supports"}]
    payload["hypotheses"] = [hypothesis]

    session = InvestigationSession.model_validate(payload)

    assert session.hypotheses[0].evidence[0].clue_id == "clue_001"


def test_hypothesis_referencing_unknown_clue_is_rejected() -> None:
    payload = analysis_session_payload()
    hypothesis = hypothesis_payload()
    hypothesis["evidence"] = [{"clue_id": "missing", "relation": "context"}]
    payload["hypotheses"] = [hypothesis]

    with pytest.raises(ValidationError, match="hypothesis_001.*unknown clue"):
        InvestigationSession.model_validate(payload)


def test_round_one_hypothesis_cannot_use_clue_revealed_in_round_two() -> None:
    payload = analysis_session_payload(two_rounds=True)
    hypothesis = hypothesis_payload(round_index=1)
    hypothesis["evidence"] = [{"clue_id": "clue_002", "relation": "supports"}]
    payload["hypotheses"] = [hypothesis]

    with pytest.raises(ValidationError, match="outside its round visibility"):
        InvestigationSession.model_validate(payload)


def test_hypothesis_may_revise_previous_round_hypothesis() -> None:
    payload = analysis_session_payload(two_rounds=True)
    payload["hypotheses"] = [
        hypothesis_payload("hypothesis_001", round_index=1),
        hypothesis_payload(
            "hypothesis_002",
            round_index=2,
            previous_hypothesis_id="hypothesis_001",
        ),
    ]

    session = InvestigationSession.model_validate(payload)

    assert session.hypotheses[1].previous_hypothesis_id == "hypothesis_001"


def test_hypothesis_may_revise_earlier_same_round_hypothesis() -> None:
    payload = analysis_session_payload()
    payload["hypotheses"] = [
        hypothesis_payload("hypothesis_001"),
        hypothesis_payload(
            "hypothesis_002",
            previous_hypothesis_id="hypothesis_001",
        ),
    ]

    assert len(InvestigationSession.model_validate(payload).hypotheses) == 2


def test_hypothesis_cannot_revise_hypothesis_from_later_round() -> None:
    payload = analysis_session_payload(two_rounds=True)
    payload["hypotheses"] = [
        hypothesis_payload("hypothesis_future", round_index=2),
        hypothesis_payload(
            "hypothesis_current",
            round_index=1,
            previous_hypothesis_id="hypothesis_future",
        ),
    ]

    with pytest.raises(ValidationError, match="later round"):
        InvestigationSession.model_validate(payload)


def test_hypothesis_revision_cycle_is_rejected() -> None:
    payload = analysis_session_payload()
    payload["hypotheses"] = [
        hypothesis_payload(
            "hypothesis_001",
            previous_hypothesis_id="hypothesis_002",
        ),
        hypothesis_payload(
            "hypothesis_002",
            previous_hypothesis_id="hypothesis_001",
        ),
    ]

    with pytest.raises(ValidationError, match="appear earlier"):
        InvestigationSession.model_validate(payload)


def test_hypothesis_cannot_revise_hypothesis_from_another_session() -> None:
    payload = analysis_session_payload()
    foreign = hypothesis_payload("hypothesis_001")
    foreign["session_id"] = "session_002"
    payload["hypotheses"] = [
        foreign,
        hypothesis_payload(
            "hypothesis_002",
            previous_hypothesis_id="hypothesis_001",
        ),
    ]

    with pytest.raises(ValidationError, match="another session"):
        InvestigationSession.model_validate(payload)


def test_multiple_independent_hypotheses_are_valid() -> None:
    payload = analysis_session_payload()
    payload["hypotheses"] = [
        hypothesis_payload("hypothesis_001"),
        hypothesis_payload("hypothesis_002"),
    ]

    assert len(InvestigationSession.model_validate(payload).hypotheses) == 2


def test_valid_decision_uses_analyses_from_own_round() -> None:
    session = InvestigationSession.model_validate(
        completed_decision_session_payload()
    )

    assert session.decisions[0].analysis_ids == ("analysis_001",)
    assert session.rounds[0].decision_id == "decision_001"


def test_decision_from_another_session_is_rejected() -> None:
    payload = completed_decision_session_payload()
    payload["decisions"][0]["session_id"] = "session_002"

    with pytest.raises(ValidationError, match="decision_001.*another session"):
        InvestigationSession.model_validate(payload)


def test_decision_referencing_unknown_round_is_rejected() -> None:
    payload = completed_decision_session_payload()
    payload["decisions"][0]["round_id"] = "round_missing"

    with pytest.raises(ValidationError, match="decision_001.*unknown round"):
        InvestigationSession.model_validate(payload)


def test_decision_referencing_unknown_analysis_is_rejected() -> None:
    payload = completed_decision_session_payload()
    payload["decisions"][0]["analysis_ids"] = ["missing"]

    with pytest.raises(ValidationError, match="unknown analysis"):
        InvestigationSession.model_validate(payload)


def test_round_one_decision_cannot_reference_round_two_analysis() -> None:
    payload = completed_decision_session_payload(two_rounds=True)
    payload["decisions"][0]["analysis_ids"] = ["analysis_002"]

    with pytest.raises(ValidationError, match="decision round"):
        InvestigationSession.model_validate(payload)


def test_round_two_decision_cannot_reference_round_one_analysis() -> None:
    payload = completed_decision_session_payload(two_rounds=True)
    payload["decisions"][1]["analysis_ids"] = ["analysis_001"]

    with pytest.raises(ValidationError, match="decision round"):
        InvestigationSession.model_validate(payload)


def test_decision_cannot_reference_analysis_from_another_session() -> None:
    payload = completed_decision_session_payload()
    payload["analyses"][0]["session_id"] = "session_002"

    with pytest.raises(ValidationError, match="analysis_001.*another session"):
        InvestigationSession.model_validate(payload)


def test_decision_analysis_must_be_listed_by_owning_round() -> None:
    payload = completed_decision_session_payload()
    payload["rounds"][0]["analysis_ids"] = []

    with pytest.raises(ValidationError, match="match session analysis order"):
        InvestigationSession.model_validate(payload)


def test_decision_may_reference_hypothesis_from_previous_round() -> None:
    payload = completed_decision_session_payload(two_rounds=True)
    payload["hypotheses"] = [hypothesis_payload(round_index=1)]
    payload["decisions"][1]["hypothesis_ids"] = ["hypothesis_001"]

    session = InvestigationSession.model_validate(payload)

    assert session.decisions[1].hypothesis_ids == ("hypothesis_001",)


def test_decision_may_reference_hypothesis_from_current_round() -> None:
    payload = completed_decision_session_payload()
    payload["hypotheses"] = [hypothesis_payload()]
    payload["decisions"][0]["hypothesis_ids"] = ["hypothesis_001"]

    assert InvestigationSession.model_validate(payload).decisions


def test_decision_cannot_reference_future_round_hypothesis() -> None:
    payload = completed_decision_session_payload(two_rounds=True)
    payload["hypotheses"] = [hypothesis_payload(round_index=2)]
    payload["decisions"][0]["hypothesis_ids"] = ["hypothesis_001"]

    with pytest.raises(ValidationError, match="future-round hypothesis"):
        InvestigationSession.model_validate(payload)


def test_decision_referencing_unknown_hypothesis_is_rejected() -> None:
    payload = completed_decision_session_payload()
    payload["decisions"][0]["hypothesis_ids"] = ["missing"]

    with pytest.raises(ValidationError, match="unknown hypothesis"):
        InvestigationSession.model_validate(payload)


def test_decision_evidence_is_limited_to_round_visibility() -> None:
    payload = completed_decision_session_payload(two_rounds=True)
    payload["decisions"][0]["evidence"] = [
        {"clue_id": "clue_002", "relation": "context"}
    ]

    with pytest.raises(ValidationError, match="outside its round visibility"):
        InvestigationSession.model_validate(payload)


def test_decision_referencing_unknown_clue_is_rejected() -> None:
    payload = completed_decision_session_payload()
    payload["decisions"][0]["evidence"] = [
        {"clue_id": "missing", "relation": "context"}
    ]

    with pytest.raises(ValidationError, match="decision_001.*unknown clue"):
        InvestigationSession.model_validate(payload)


def test_two_decisions_for_one_round_are_rejected() -> None:
    payload = completed_decision_session_payload()
    payload["decisions"].append(decision_payload("decision_002"))

    with pytest.raises(ValidationError, match="at most one group decision"):
        InvestigationSession.model_validate(payload)


def test_round_referencing_unknown_decision_is_rejected() -> None:
    payload = analysis_session_payload()
    payload["rounds"][0]["decision_id"] = "missing"
    payload["rounds"][0]["status"] = "completed"

    with pytest.raises(ValidationError, match="unknown decision"):
        InvestigationSession.model_validate(payload)


def test_decision_omitted_from_owning_round_is_rejected() -> None:
    payload = completed_decision_session_payload()
    payload["rounds"][0]["decision_id"] = None
    payload["rounds"][0]["status"] = "awaiting_decision"

    with pytest.raises(ValidationError, match="referenced by its owning round"):
        InvestigationSession.model_validate(payload)


def test_round_cannot_reference_decision_from_another_round() -> None:
    payload = completed_decision_session_payload(two_rounds=True)
    payload["rounds"][0]["decision_id"] = "decision_002"

    with pytest.raises(ValidationError, match="another round"):
        InvestigationSession.model_validate(payload)


def test_completed_round_requires_decision() -> None:
    payload = analysis_session_payload()
    payload["rounds"][0]["status"] = "completed"

    with pytest.raises(ValidationError, match="completed rounds require"):
        InvestigationSession.model_validate(payload)


@pytest.mark.parametrize(
    "status",
    ["awaiting_analyses", "awaiting_discussion", "awaiting_decision"],
)
def test_non_completed_round_cannot_link_decision(status: str) -> None:
    payload = completed_decision_session_payload()
    payload["rounds"][0]["status"] = status

    with pytest.raises(ValidationError, match="non-completed rounds"):
        InvestigationSession.model_validate(payload)


def test_completed_round_does_not_require_hypotheses() -> None:
    payload = completed_decision_session_payload()

    session = InvestigationSession.model_validate(payload)

    assert session.hypotheses == ()
    assert session.decisions[0].hypothesis_ids == ()


def test_two_completed_rounds_preserve_complete_graph_in_json() -> None:
    payload = completed_decision_session_payload(two_rounds=True)
    payload["hypotheses"] = [
        hypothesis_payload("hypothesis_001", round_index=1),
        hypothesis_payload(
            "hypothesis_002",
            round_index=2,
            previous_hypothesis_id="hypothesis_001",
        ),
    ]
    payload["decisions"][0]["hypothesis_ids"] = ["hypothesis_001"]
    payload["decisions"][1]["hypothesis_ids"] = [
        "hypothesis_001",
        "hypothesis_002",
    ]
    session = InvestigationSession.model_validate(payload)

    serialized = session.model_dump_json()
    restored = InvestigationSession.model_validate_json(serialized)

    assert restored == session
    assert restored.model_dump_json() == serialized
    assert tuple(item.decision_id for item in restored.rounds) == (
        "decision_001",
        "decision_002",
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
    assert len(session.analyses) == 2
    assert len(session.hypotheses) == 2
    assert len(session.decisions) == 2
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
            {
                "analysis_id": "same",
                "session_id": "session_001",
                "round_id": "round_001",
                "agent_id": "sherlock",
                "visible_clue_ids": ["clue_001"],
                "facts": ["A"],
            },
        ),
        (
            "hypotheses",
            "hypothesis_id",
            {
                "hypothesis_id": "same",
                "session_id": "session_001",
                "round_id": "round_001",
                "statement": "A",
                "status": "active",
            },
        ),
        (
            "decisions",
            "decision_id",
            {
                "decision_id": "same",
                "session_id": "session_001",
                "round_id": "round_001",
                "decision_type": "pursue_lead",
                "summary": "A",
            },
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
    if collection == "analyses":
        payload["clues"] = [
            {"clue_id": "clue_001", "text": "First", "reveal_order": 0}
        ]
        payload["rounds"] = [
            {
                "session_id": "session_001",
                "round_id": "round_001",
                "round_index": 1,
                "revealed_clue_id": "clue_001",
                "visible_clue_ids": ["clue_001"],
                "status": "awaiting_analyses",
            }
        ]
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
    payload = analysis_session_payload()
    payload["analyses"] = [
        analysis_payload(agent_id="outsider")
    ]
    payload["rounds"][0]["analysis_ids"] = ["analysis_001"]

    with pytest.raises(ValidationError, match="participants"):
        InvestigationSession.model_validate(payload)


@pytest.mark.parametrize("entity", ["analyses", "hypotheses", "decisions", "final_theory"])
def test_unknown_clue_reference_is_rejected_for_every_entity(entity: str) -> None:
    payload = minimal_payload("active")
    evidence = [{"clue_id": "missing", "relation": "context"}]
    if entity == "analyses":
        payload["clues"] = [
            {"clue_id": "clue_001", "text": "First", "reveal_order": 0}
        ]
        payload["rounds"] = [round_payload_for_analysis()]
        payload[entity] = [
            {
                **analysis_payload(),
                "evidence": evidence,
            }
        ]
        payload["rounds"][0]["analysis_ids"] = ["analysis_001"]
    elif entity == "hypotheses":
        payload["clues"] = [
            {"clue_id": "clue_001", "text": "First", "reveal_order": 0}
        ]
        payload["rounds"] = [round_payload_for_analysis()]
        payload[entity] = [
            {**hypothesis_payload(), "evidence": evidence}
        ]
    elif entity == "decisions":
        payload["clues"] = [
            {"clue_id": "clue_001", "text": "First", "reveal_order": 0}
        ]
        decision_round = round_payload_for_analysis()
        decision_round["decision_id"] = "decision_001"
        decision_round["status"] = "completed"
        payload["rounds"] = [decision_round]
        payload[entity] = [
            {**decision_payload(), "evidence": evidence}
        ]
    else:
        payload[entity] = {"final_theory_id": "final_001", "summary": "A", "evidence": evidence}

    expected_error = (
        "unknown clue" if entity != "final_theory" else "session clues"
    )
    with pytest.raises(ValidationError, match=expected_error):
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
    payload = analysis_session_payload()
    decision_round = payload["rounds"][0]
    decision_round["decision_id"] = "decision_001"
    decision_round["status"] = "completed"
    payload["decisions"] = [
        {
            **decision_payload(),
            field_name: [value],
        }
    ]

    with pytest.raises(ValidationError, match=message):
        InvestigationSession.model_validate(payload)


def test_unknown_previous_hypothesis_is_rejected() -> None:
    payload = analysis_session_payload()
    payload["hypotheses"] = [
        {
            **hypothesis_payload("hypothesis_002"),
            "previous_hypothesis_id": "missing",
        }
    ]

    with pytest.raises(ValidationError, match="must exist"):
        InvestigationSession.model_validate(payload)


def test_forward_hypothesis_revision_reference_is_rejected() -> None:
    payload = analysis_session_payload()
    payload["hypotheses"] = [
        {
            **hypothesis_payload("hypothesis_002"),
            "statement": "Revision first.",
            "previous_hypothesis_id": "hypothesis_001",
        },
        {
            **hypothesis_payload("hypothesis_001"),
            "statement": "Original.",
            "status": "discarded",
        },
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
