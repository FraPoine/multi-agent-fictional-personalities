"""Validated local catalogue of synthetic investigation case definitions."""

from pathlib import Path
from typing import Annotated

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)


NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]
CaseKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$",
        strict=True,
    ),
]


def _duplicates(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


class CaseLeadDefinition(BaseModel):
    """One static lead reference declared by a local case definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lead_key: CaseKey
    reference: NonEmptyStr
    reference_scheme: NonEmptyStr
    label: NonEmptyStr
    kind: NonEmptyStr


class CaseDefinition(BaseModel):
    """Static case configuration copied only by provenance into a session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: CaseKey
    title: NonEmptyStr
    short_description: NonEmptyStr
    opening: NonEmptyStr
    leads: tuple[CaseLeadDefinition, ...] = ()
    resource_refs: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_unique_case_references(self) -> "CaseDefinition":
        duplicate_keys = _duplicates([lead.lead_key for lead in self.leads])
        if duplicate_keys:
            raise ValueError(
                "duplicate lead_key value(s): " + ", ".join(duplicate_keys)
            )
        duplicate_references = _duplicates(
            [lead.reference for lead in self.leads]
        )
        if duplicate_references:
            raise ValueError(
                "duplicate lead reference(s): "
                + ", ".join(duplicate_references)
            )
        duplicate_resources = _duplicates(list(self.resource_refs))
        if duplicate_resources:
            raise ValueError(
                "duplicate resource_refs value(s): "
                + ", ".join(duplicate_resources)
            )
        return self


class CaseCatalog(BaseModel):
    """Deterministically ordered collection of unique local cases."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cases: tuple[CaseDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> "CaseCatalog":
        duplicates = _duplicates([case.case_id for case in self.cases])
        if duplicates:
            raise ValueError(
                "duplicate case_id value(s): " + ", ".join(duplicates)
            )
        return self

    def get(self, case_id: str) -> CaseDefinition:
        """Return one case by stable ID or raise a clear lookup error."""
        for case in self.cases:
            if case.case_id == case_id:
                return case
        raise KeyError(f"unknown case_id: {case_id!r}")


def default_case_catalog_directory(project_root: Path) -> Path:
    """Return the repository-local case definition directory."""
    return (
        Path(project_root).resolve()
        / "configs"
        / "investigation"
        / "cases"
    )


def load_case_catalog(catalog_directory: Path) -> CaseCatalog:
    """Load sorted local YAML case files without network or mutable state."""
    directory = Path(catalog_directory).resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"case catalogue directory not found: {directory}")
    paths = tuple(sorted((*directory.glob("*.yaml"), *directory.glob("*.yml"))))
    if not paths:
        raise ValueError(f"case catalogue contains no YAML files: {directory}")

    cases: list[CaseDefinition] = []
    for path in paths:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise OSError(f"could not read case definition {path}: {error}") from error
        except yaml.YAMLError as error:
            raise ValueError(f"invalid YAML in case definition {path}: {error}") from error
        if not isinstance(raw, dict):
            raise ValueError(f"case definition {path} must contain a mapping")
        try:
            cases.append(CaseDefinition.model_validate(raw))
        except ValidationError as error:
            raise ValueError(f"invalid case definition {path}: {error}") from error

    try:
        return CaseCatalog(cases=tuple(cases))
    except ValidationError as error:
        raise ValueError(f"invalid case catalogue {directory}: {error}") from error

