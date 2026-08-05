"""Validated, configuration-driven catalog of supported runtime characters."""

from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from multi_agent_personalities.models.persona import Persona


NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]
CharacterSlug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$",
        strict=True,
    ),
]


class CharacterCatalogEntry(BaseModel):
    """One supported character and its resolved local runtime assets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slug: CharacterSlug
    character_id: NonEmptyStr
    display_name: NonEmptyStr
    description: NonEmptyStr
    corpus_path: Path
    persona_fixture_path: Path
    mock_response_fixture_path: Path


class CharacterCatalog(BaseModel):
    """An ordered, non-empty collection of unique character entries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    characters: tuple[CharacterCatalogEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_identities(self) -> "CharacterCatalog":
        slugs = [entry.slug for entry in self.characters]
        duplicate_slugs = _duplicates(slugs)
        if duplicate_slugs:
            raise ValueError(
                "duplicate character slug(s): " + ", ".join(duplicate_slugs)
            )

        character_ids = [entry.character_id for entry in self.characters]
        duplicate_ids = _duplicates(character_ids)
        if duplicate_ids:
            raise ValueError(
                "duplicate character_id value(s): " + ", ".join(duplicate_ids)
            )
        return self


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def default_character_catalog_path(project_root: Path) -> Path:
    """Return the repository catalog path without using the current directory."""

    return Path(project_root).resolve() / "configs" / "characters.yaml"


def load_character_catalog(catalog_path: Path) -> CharacterCatalog:
    """Load a catalog whose declared paths are relative to its parent directory.

    YAML is parsed with ``safe_load``. Every referenced path is resolved to an
    absolute path, must identify an existing regular file, and is returned in
    declared order. Persona identity is checked while the catalog is loaded so
    invalid runtime configuration fails before a conversation begins.
    """

    resolved_catalog_path = Path(catalog_path).resolve()
    if not resolved_catalog_path.is_file():
        raise FileNotFoundError(
            f"character catalog file not found: {resolved_catalog_path}"
        )

    try:
        raw_data = yaml.safe_load(resolved_catalog_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(
            f"could not read character catalog {resolved_catalog_path}: {error}"
        ) from error
    except yaml.YAMLError as error:
        raise ValueError(
            f"invalid YAML in character catalog {resolved_catalog_path}: {error}"
        ) from error

    if not isinstance(raw_data, dict):
        raise ValueError(
            f"character catalog {resolved_catalog_path} must contain a mapping"
        )

    prepared_data = _resolve_declared_paths(
        raw_data,
        base_directory=resolved_catalog_path.parent,
    )
    try:
        catalog = CharacterCatalog.model_validate(prepared_data)
    except ValidationError as error:
        raise ValueError(
            f"invalid character catalog {resolved_catalog_path}: {error}"
        ) from error

    for entry in catalog.characters:
        _validate_entry_files(entry)
        _validate_persona_identity(entry)
    return catalog


def _resolve_declared_paths(
    raw_data: dict[str, Any],
    *,
    base_directory: Path,
) -> dict[str, Any]:
    characters = raw_data.get("characters")
    if not isinstance(characters, list):
        return raw_data

    prepared_characters: list[Any] = []
    path_fields = (
        "corpus_path",
        "persona_fixture_path",
        "mock_response_fixture_path",
    )
    for raw_entry in characters:
        if not isinstance(raw_entry, dict):
            prepared_characters.append(raw_entry)
            continue
        prepared_entry = dict(raw_entry)
        for field_name in path_fields:
            declared_path = prepared_entry.get(field_name)
            if isinstance(declared_path, str):
                prepared_entry[field_name] = (
                    base_directory / declared_path
                ).resolve()
        prepared_characters.append(prepared_entry)

    prepared_data = dict(raw_data)
    prepared_data["characters"] = prepared_characters
    return prepared_data


def _validate_entry_files(entry: CharacterCatalogEntry) -> None:
    for field_name in (
        "corpus_path",
        "persona_fixture_path",
        "mock_response_fixture_path",
    ):
        path = getattr(entry, field_name)
        if not path.exists():
            raise FileNotFoundError(
                f"{field_name} for character {entry.slug!r} does not exist: {path}"
            )
        if not path.is_file():
            raise ValueError(
                f"{field_name} for character {entry.slug!r} must be a file: {path}"
            )


def _validate_persona_identity(entry: CharacterCatalogEntry) -> None:
    try:
        persona = Persona.model_validate_json(
            entry.persona_fixture_path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as error:
        raise ValueError(
            f"invalid persona_fixture_path for character {entry.slug!r}: {error}"
        ) from error

    if (persona.character_id, persona.display_name) != (
        entry.character_id,
        entry.display_name,
    ):
        raise ValueError(
            f"persona fixture identity does not match catalog entry {entry.slug!r}"
        )
