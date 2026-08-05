"""Tests for immutable investigation building-block models."""

import pytest
from pydantic import ValidationError

from multi_agent_personalities.models import (
    Clue,
    EvidenceReference,
    EvidenceRelation,
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
