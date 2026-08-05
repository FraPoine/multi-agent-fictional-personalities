"""Tests for the validated supported-character catalog."""

from pathlib import Path

import pytest
import yaml

from multi_agent_personalities.character_catalog import (
    CharacterCatalogEntry,
    default_character_catalog_path,
    load_character_catalog,
)
from multi_agent_personalities.application import run_mock_conversation
from multi_agent_personalities.pipeline import character_registry


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def create_character_assets(
    root: Path,
    *,
    slug: str,
    character_id: str,
    display_name: str,
) -> dict[str, str]:
    asset_directory = root / "assets" / slug
    asset_directory.mkdir(parents=True)
    corpus = asset_directory / "corpus.jsonl"
    corpus.write_text(
        '{"text":"A deterministic corpus example."}\n',
        encoding="utf-8",
    )
    persona = asset_directory / "persona.json"
    persona.write_text(
        """{
  "character_id": "%s",
  "display_name": "%s",
  "description": "Synthetic test persona.",
  "speaking_style": ["Precise"],
  "reasoning_style": ["Methodical"],
  "personality_traits": ["Observant"],
  "behavior_rules": ["Use available evidence"],
  "example_messages": ["A synthetic example."]
}
""" % (character_id, display_name),
        encoding="utf-8",
    )
    response = asset_directory / "response.txt"
    response.write_text(f"A response from {display_name}.\n", encoding="utf-8")
    return {
        "slug": slug,
        "character_id": character_id,
        "display_name": display_name,
        "description": f"Synthetic configuration for {display_name}.",
        "corpus_path": f"../assets/{slug}/corpus.jsonl",
        "persona_fixture_path": f"../assets/{slug}/persona.json",
        "mock_response_fixture_path": f"../assets/{slug}/response.txt",
    }


def write_catalog(root: Path, entries: list[dict[str, str]]) -> Path:
    config_directory = root / "configs"
    config_directory.mkdir(parents=True, exist_ok=True)
    path = config_directory / "characters.yaml"
    path.write_text(
        yaml.safe_dump({"characters": entries}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def two_valid_entries(root: Path) -> list[dict[str, str]]:
    (root / "configs").mkdir(parents=True, exist_ok=True)
    return [
        create_character_assets(
            root,
            slug="zeta",
            character_id="zeta_detective",
            display_name="Zeta Detective",
        ),
        create_character_assets(
            root,
            slug="alpha",
            character_id="alpha_detective",
            display_name="Alpha Detective",
        ),
    ]


def test_valid_catalog_loads_typed_entries_and_resolves_paths(
    tmp_path: Path,
) -> None:
    catalog_path = write_catalog(tmp_path, two_valid_entries(tmp_path))

    catalog = load_character_catalog(catalog_path)

    assert all(
        isinstance(entry, CharacterCatalogEntry) for entry in catalog.characters
    )
    assert [entry.slug for entry in catalog.characters] == ["zeta", "alpha"]
    assert all(entry.corpus_path.is_absolute() for entry in catalog.characters)
    assert all(entry.corpus_path.is_file() for entry in catalog.characters)


@pytest.mark.parametrize(
    ("duplicate_field", "error"),
    [
        ("slug", "duplicate character slug"),
        ("character_id", "duplicate character_id"),
    ],
)
def test_duplicate_identity_is_rejected(
    tmp_path: Path,
    duplicate_field: str,
    error: str,
) -> None:
    entries = two_valid_entries(tmp_path)
    entries[1][duplicate_field] = entries[0][duplicate_field]

    with pytest.raises(ValueError, match=error):
        load_character_catalog(write_catalog(tmp_path, entries))


def test_missing_required_field_is_rejected(tmp_path: Path) -> None:
    entries = two_valid_entries(tmp_path)
    del entries[0]["display_name"]

    with pytest.raises(ValueError, match="display_name"):
        load_character_catalog(write_catalog(tmp_path, entries))


def test_nonexistent_path_identifies_field_and_character(tmp_path: Path) -> None:
    entries = two_valid_entries(tmp_path)
    entries[0]["corpus_path"] = "../assets/zeta/missing.jsonl"

    with pytest.raises(
        FileNotFoundError,
        match="corpus_path for character 'zeta' does not exist",
    ):
        load_character_catalog(write_catalog(tmp_path, entries))


def test_directory_is_rejected_when_file_is_required(tmp_path: Path) -> None:
    entries = two_valid_entries(tmp_path)
    entries[0]["mock_response_fixture_path"] = "../assets/zeta"

    with pytest.raises(ValueError, match="mock_response_fixture_path.*must be a file"):
        load_character_catalog(write_catalog(tmp_path, entries))


def test_registry_preserves_non_alphabetical_catalog_order(tmp_path: Path) -> None:
    write_catalog(tmp_path, two_valid_entries(tmp_path))

    registry = character_registry(tmp_path)

    assert list(registry) == ["zeta", "alpha"]


def test_synthetic_third_character_requires_only_catalog_and_assets(
    tmp_path: Path,
) -> None:
    entries = two_valid_entries(tmp_path)
    entries.append(
        create_character_assets(
            tmp_path,
            slug="third",
            character_id="synthetic_third",
            display_name="Synthetic Third",
        )
    )
    write_catalog(tmp_path, entries)

    registry = character_registry(tmp_path)

    assert list(registry) == ["zeta", "alpha", "third"]
    assert registry["third"].character_id == "synthetic_third"
    assert registry["third"].agent_response_fixture.read_text(
        encoding="utf-8"
    ) == "A response from Synthetic Third.\n"

    result = run_mock_conversation(
        character_slugs=["zeta", "alpha", "third"],
        topic="A deterministic synthetic case.",
        turn_count=3,
        project_root=tmp_path,
        output_root=tmp_path / "outputs",
        run_id="synthetic_catalog_run",
    )
    assert result.run.character_ids == (
        "zeta_detective",
        "alpha_detective",
        "synthetic_third",
    )


def test_persona_catalog_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    entries = two_valid_entries(tmp_path)
    entries[0]["character_id"] = "different_identity"

    with pytest.raises(ValueError, match="identity does not match.*'zeta'"):
        load_character_catalog(write_catalog(tmp_path, entries))


def test_default_catalog_contains_only_current_characters_in_order() -> None:
    catalog = load_character_catalog(
        default_character_catalog_path(REPOSITORY_ROOT)
    )

    assert [entry.slug for entry in catalog.characters] == [
        "sherlock",
        "poirot",
    ]
    assert [entry.character_id for entry in catalog.characters] == [
        "sherlock_holmes",
        "hercule_poirot",
    ]
    assert all(
        path.is_file()
        for entry in catalog.characters
        for path in (
            entry.corpus_path,
            entry.persona_fixture_path,
            entry.mock_response_fixture_path,
        )
    )
