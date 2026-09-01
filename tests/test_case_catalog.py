"""Tests for the deterministic local investigation case catalogue."""

import socket
from pathlib import Path

import pytest

from multi_agent_personalities.case_catalog import (
    CaseCatalog,
    default_case_catalog_directory,
    load_case_catalog,
)
from multi_agent_personalities.web.investigation_store import (
    InMemoryInvestigationRegistry,
)


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ("sherlock", "poirot")


def write_case(directory: Path, filename: str, *, case_id: str, reference: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(
        "\n".join(
            (
                f"case_id: {case_id}",
                f"title: Case {case_id}",
                "short_description: A local synthetic case.",
                "opening: A synthetic opening.",
                "leads:",
                "  - lead_key: first-lead",
                f"    reference: {reference}",
                "    reference_scheme: london-address",
                "    label: First Lead",
                "    kind: place",
                "resource_refs: []",
            )
        ),
        encoding="utf-8",
    )


def test_repository_catalogue_loads_multiple_synthetic_cases_in_file_order() -> None:
    catalogue = load_case_catalog(default_case_catalog_directory(ROOT))

    assert isinstance(catalogue, CaseCatalog)
    assert [case.case_id for case in catalogue.cases] == [
        "archive-absence",
        "observatory-signal",
    ]
    assert all(case.leads for case in catalogue.cases)


def test_duplicate_case_id_is_rejected(tmp_path: Path) -> None:
    write_case(tmp_path, "a.yaml", case_id="same-case", reference="42 NW")
    write_case(tmp_path, "b.yaml", case_id="same-case", reference="95 NW")

    with pytest.raises(ValueError, match="duplicate case_id"):
        load_case_catalog(tmp_path)


@pytest.mark.parametrize(
    ("duplicate_field", "expected"),
    (("lead_key", "duplicate lead_key"), ("reference", "duplicate lead reference")),
)
def test_duplicate_lead_identity_within_one_case_is_rejected(
    tmp_path: Path, duplicate_field: str, expected: str
) -> None:
    first_key, second_key = "lead-a", "lead-b"
    first_reference, second_reference = "42 NW", "95 NW"
    if duplicate_field == "lead_key":
        second_key = first_key
    else:
        second_reference = first_reference
    (tmp_path / "case.yaml").write_text(
        f"""case_id: duplicate-lead-case
title: Duplicate lead case
short_description: Synthetic validation input.
opening: A synthetic opening.
leads:
  - lead_key: {first_key}
    reference: {first_reference}
    reference_scheme: london-address
    label: First
    kind: place
  - lead_key: {second_key}
    reference: {second_reference}
    reference_scheme: london-address
    label: Second
    kind: person
resource_refs: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=expected):
        load_case_catalog(tmp_path)


def test_same_lead_reference_is_allowed_across_cases(tmp_path: Path) -> None:
    write_case(tmp_path, "a.yaml", case_id="case-a", reference="42 NW")
    write_case(tmp_path, "b.yaml", case_id="case-b", reference="42 NW")

    catalogue = load_case_catalog(tmp_path)

    assert len(catalogue.cases) == 2
    assert catalogue.cases[0].leads[0].reference == "42 NW"
    assert catalogue.cases[1].leads[0].reference == "42 NW"


@pytest.mark.parametrize(
    "contents",
    (
        "- not-a-mapping\n",
        "case_id: [unterminated\n",
        "case_id: missing-required-fields\n",
    ),
)
def test_malformed_case_configuration_is_rejected(
    tmp_path: Path, contents: str
) -> None:
    (tmp_path / "broken.yaml").write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match="case definition"):
        load_case_catalog(tmp_path)


def test_catalogue_loader_is_local_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    catalogue = load_case_catalog(default_case_catalog_directory(ROOT))

    assert len(catalogue.cases) == 2


def test_registry_copies_case_provenance_and_isolates_same_case_sessions() -> None:
    catalogue = load_case_catalog(default_case_catalog_directory(ROOT))
    definition = catalogue.get("archive-absence")
    registry = InMemoryInvestigationRegistry(case_catalog=catalogue)

    first = registry.create(
        character_slugs=CHARACTERS,
        case_id=definition.case_id,
        project_root=ROOT,
    )
    second = registry.create(
        character_slugs=CHARACTERS,
        case_id=definition.case_id,
        project_root=ROOT,
    )

    assert first.session.case_id == second.session.case_id == definition.case_id
    assert first.session.case_introduction == definition.opening
    assert second.session.case_introduction == definition.opening
    assert first.session.session_id != second.session.session_id
    assert first.session is not second.session


def test_reloading_changed_definition_does_not_mutate_existing_session(
    tmp_path: Path,
) -> None:
    write_case(tmp_path, "case.yaml", case_id="stable-case", reference="42 NW")
    registry = InMemoryInvestigationRegistry(
        case_catalog=load_case_catalog(tmp_path)
    )
    existing = registry.create(
        character_slugs=CHARACTERS,
        case_id="stable-case",
        project_root=ROOT,
    )

    path = tmp_path / "case.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "A synthetic opening.", "A changed opening."
        ),
        encoding="utf-8",
    )
    reloaded = load_case_catalog(tmp_path)

    assert reloaded.get("stable-case").opening == "A changed opening."
    assert existing.session.case_introduction == "A synthetic opening."
    assert registry.snapshot(existing.session_id) is existing.session
