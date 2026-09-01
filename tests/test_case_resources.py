"""Validated case-aware resource catalogue and presentation tests."""

import socket
from pathlib import Path

import pytest
from pydantic import ValidationError

from multi_agent_personalities.case_catalog import (
    CaseCatalog,
    CaseDefinition,
    CaseResourceDefinition,
    CaseResourceType,
    default_case_catalog_directory,
    load_case_catalog,
)
from multi_agent_personalities.web.investigation_presentation import present_session
from multi_agent_personalities.web.investigation_store import InMemoryInvestigationRegistry


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ("sherlock", "poirot")


def test_resource_schema_validates_type_date_and_safe_relative_assets() -> None:
    resource = CaseResourceDefinition(
        resource_id="dated-paper",
        type=CaseResourceType.NEWSPAPER,
        title="Synthetic Daily",
        date="1889-03-14",
        asset_path=Path("assets/paper-placeholder.pdf"),
    )

    assert resource.type is CaseResourceType.NEWSPAPER
    assert resource.date.isoformat() == "1889-03-14"
    with pytest.raises(ValidationError, match="safe local relative path"):
        CaseResourceDefinition(
            resource_id="unsafe",
            type="map",
            title="Unsafe",
            asset_path="../outside.svg",
        )


def test_unknown_case_resource_reference_is_rejected() -> None:
    case = CaseDefinition(
        case_id="unknown-resource-case",
        title="Unknown resource",
        short_description="Synthetic validation case.",
        opening="A synthetic opening.",
        resource_refs=("missing-resource",),
    )

    with pytest.raises(ValidationError, match="unknown resource_id"):
        CaseCatalog(cases=(case,))


def test_case_resource_sets_preserve_map_order_and_share_definitions() -> None:
    catalogue = load_case_catalog(default_case_catalog_directory(ROOT))
    archive = catalogue.resources_for_case("archive-absence")
    observatory = catalogue.resources_for_case("observatory-signal")

    assert [item.resource_id for item in archive if item.type is CaseResourceType.MAP] == [
        "london-overview",
        "archive-district",
    ]
    assert [
        item.resource_id for item in observatory if item.type is CaseResourceType.MAP
    ] == ["observatory-plan"]
    assert {item.resource_id for item in archive} != {
        item.resource_id for item in observatory
    }
    for shared in ("london-directory", "recurring-informants"):
        assert shared in {item.resource_id for item in archive}
        assert shared in {item.resource_id for item in observatory}


def test_presentation_filters_hidden_handout_and_handles_one_or_many_maps() -> None:
    catalogue = load_case_catalog(default_case_catalog_directory(ROOT))
    registry = InMemoryInvestigationRegistry(case_catalog=catalogue)
    archive = registry.create(
        character_slugs=CHARACTERS,
        case_id="archive-absence",
        project_root=ROOT,
    )
    observatory = registry.create(
        character_slugs=CHARACTERS,
        case_id="observatory-signal",
        project_root=ROOT,
    )
    resource_base = default_case_catalog_directory(ROOT).parent

    archive_view = present_session(
        archive,
        case_catalog=catalogue,
        resource_base_directory=resource_base,
    )
    observatory_view = present_session(
        observatory,
        case_catalog=catalogue,
        resource_base_directory=resource_base,
    )
    archive_maps = next(
        group for group in archive_view.resource_groups if group.key == "resources-map"
    )
    observatory_maps = next(
        group
        for group in observatory_view.resource_groups
        if group.key == "resources-map"
    )

    assert archive_maps.map_selector is True
    assert [item.resource_id for item in archive_maps.resources] == [
        "london-overview",
        "archive-district",
    ]
    assert observatory_maps.map_selector is False
    assert [item.resource_id for item in observatory_maps.resources] == [
        "observatory-plan"
    ]
    visible_ids = {
        item.resource_id
        for group in archive_view.resource_groups
        for item in group.resources
    }
    assert "sealed-handout" not in visible_ids
    archive_detail = next(
        item
        for item in archive_maps.resources
        if item.resource_id == "archive-district"
    )
    assert archive_detail.asset_available is False


def test_resource_loading_requires_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    catalogue = load_case_catalog(default_case_catalog_directory(ROOT))

    assert catalogue.resources

