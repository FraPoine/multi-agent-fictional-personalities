"""Tests for deterministic investigation identifier ownership."""

from dataclasses import FrozenInstanceError

import pytest

from multi_agent_personalities.application import (
    DeterministicInvestigationIdFactory,
    create_session,
)


def test_factory_builds_valid_one_based_deterministic_ids() -> None:
    factory = DeterministicInvestigationIdFactory(1)

    assert factory.session_id == "session_001"
    assert factory.clue_id(0) == "session_001_clue_0001"
    assert factory.clue_id(1) == "session_001_clue_0002"
    assert factory.lead_id(1) == "session_001_lead_0001"
    assert factory.visit_id(1) == "session_001_visit_0001"
    assert factory.information_id(0) == "session_001_info_0001"
    assert factory.discussion_segment_id(1, 1) == (
        "session_001_visit_0001_discussion_0001"
    )
    assert factory.round_id(1) == "session_001_round_0001"
    assert factory.analysis_id("sherlock_holmes", 1) == (
        "session_001_analysis_sherlock_holmes_0001"
    )
    assert factory.hypothesis_id(1) == "session_001_hypothesis_0001"
    assert factory.discussion_run_id(1) == (
        "session_001_round_0001_discussion"
    )
    assert factory.decision_id(1) == "session_001_decision_0001"
    assert factory.final_theory_id() == "session_001_final_theory"
    assert factory == DeterministicInvestigationIdFactory(1)


@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1"])
def test_factory_rejects_non_positive_or_non_strict_session_sequence(
    value: object,
) -> None:
    with pytest.raises(ValueError, match="session_sequence"):
        DeterministicInvestigationIdFactory(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [-1, True, 0.0, "0"])
def test_factory_rejects_invalid_reveal_order(value: object) -> None:
    with pytest.raises(ValueError, match="reveal_order"):
        DeterministicInvestigationIdFactory(1).clue_id(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1"])
def test_factory_rejects_invalid_round_index(value: object) -> None:
    with pytest.raises(ValueError, match="round_index"):
        DeterministicInvestigationIdFactory(1).round_id(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1"])
def test_factory_rejects_invalid_analysis_round_index(value: object) -> None:
    with pytest.raises(ValueError, match="round_index"):
        DeterministicInvestigationIdFactory(1).analysis_id(
            "sherlock_holmes", value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1"])
def test_factory_rejects_invalid_decision_round_index(value: object) -> None:
    with pytest.raises(ValueError, match="round_index"):
        DeterministicInvestigationIdFactory(1).decision_id(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1"])
def test_factory_rejects_invalid_hypothesis_index(value: object) -> None:
    with pytest.raises(ValueError, match="hypothesis_index"):
        DeterministicInvestigationIdFactory(1).hypothesis_id(value)  # type: ignore[arg-type]


def test_factory_is_immutable() -> None:
    factory = DeterministicInvestigationIdFactory(1)

    with pytest.raises(FrozenInstanceError):
        factory.session_sequence = 2


def test_lead_visit_and_information_ids_are_session_scoped_and_deterministic() -> None:
    first = DeterministicInvestigationIdFactory(1)
    second = DeterministicInvestigationIdFactory(2)

    assert first.lead_id(1) == DeterministicInvestigationIdFactory(1).lead_id(1)
    assert first.visit_id(2) == "session_001_visit_0002"
    assert first.information_id(1) == "session_001_info_0002"
    assert second.lead_id(1) == "session_002_lead_0001"
    assert second.visit_id(1) == "session_002_visit_0001"
    assert second.information_id(0) == "session_002_info_0001"
    assert first.lead_id(1) == first.lead_id(1)
    assert first.visit_id(1) != first.visit_id(2)


@pytest.mark.parametrize(
    ("method_name", "value", "message"),
    [
        ("lead_id", 0, "lead_index"),
        ("visit_id", 0, "visit_index"),
        ("information_id", -1, "reveal_index"),
        ("lead_id", True, "lead_index"),
        ("visit_id", 1.0, "visit_index"),
        ("information_id", "0", "reveal_index"),
    ],
)
def test_factory_rejects_invalid_new_entity_indexes(
    method_name: str, value: object, message: str
) -> None:
    method = getattr(DeterministicInvestigationIdFactory(1), method_name)
    with pytest.raises(ValueError, match=message):
        method(value)


def test_create_session_rejects_namespace_that_cannot_build_all_initial_ids() -> None:
    factory = DeterministicInvestigationIdFactory(int("9" * 130))

    with pytest.raises(ValueError, match="run_id"):
        create_session(
            id_factory=factory,
            introduction="A case.",
            participant_ids=("sherlock", "poirot"),
        )
