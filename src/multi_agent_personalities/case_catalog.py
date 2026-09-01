"""Validated local catalogue of synthetic investigation case definitions."""

from pathlib import Path
import re
from datetime import date as Date
from enum import Enum
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
LONDON_ADDRESS_SCHEME = "london-address"
CARLTON_INTERIOR_SCHEME = "carlton-interior"


def normalize_london_address_reference(raw_reference: str) -> str:
    """Normalize supported London address aliases to ``number AREA``."""
    if not isinstance(raw_reference, str) or not raw_reference.strip():
        raise ValueError("lead reference must not be empty")
    compact = re.sub(r"[\s-]+", "", raw_reference).upper()
    match = re.fullmatch(r"(?:(\d+)(NW|WC|SW|EC|SE)|(NW|WC|SW|EC|SE)(\d+))", compact)
    if match is None:
        raise ValueError("invalid London address reference")
    number = match.group(1) or match.group(4)
    area = match.group(2) or match.group(3)
    return f"{number} {area}"


def normalize_carlton_interior_reference(raw_reference: str) -> str:
    """Normalize supported interior aliases to ``FLOOR-number``."""
    if not isinstance(raw_reference, str) or not raw_reference.strip():
        raise ValueError("lead reference must not be empty")
    compact = re.sub(r"[\s-]+", "", raw_reference).upper()
    match = re.fullmatch(r"(GF|FF|BF)(\d+)", compact)
    if match is None:
        raise ValueError("invalid Carlton interior reference")
    return f"{match.group(1)}-{match.group(2)}"


def normalize_case_lead_reference(reference_scheme: str, raw_reference: str) -> str:
    """Normalize a reference with its explicitly declared structural scheme."""
    if reference_scheme == LONDON_ADDRESS_SCHEME:
        return normalize_london_address_reference(raw_reference)
    if reference_scheme == CARLTON_INTERIOR_SCHEME:
        return normalize_carlton_interior_reference(raw_reference)
    raise ValueError(f"unsupported lead reference_scheme: {reference_scheme!r}")


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

    @model_validator(mode="after")
    def validate_canonical_reference(self) -> "CaseLeadDefinition":
        canonical = normalize_case_lead_reference(
            self.reference_scheme, self.reference
        )
        if self.reference != canonical:
            raise ValueError(f"reference must use canonical form {canonical!r}")
        return self


class CaseResourceType(str, Enum):
    """Supported structural categories for local case resources."""

    MAP = "map"
    NEWSPAPER = "newspaper"
    DIRECTORY = "directory"
    INFORMANTS = "informants"
    DOCUMENT = "document"
    HANDOUT = "handout"


class CaseResourceDefinition(BaseModel):
    """One reusable local resource definition without embedded content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_id: CaseKey
    type: CaseResourceType
    title: NonEmptyStr
    asset_path: Path | None = None
    date: Date | None = None
    initially_available: bool = True
    description: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_local_asset_path(self) -> "CaseResourceDefinition":
        if self.asset_path is None:
            return self
        path = self.asset_path
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("asset_path must be a safe local relative path")
        return self


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
    resources: tuple[CaseResourceDefinition, ...] = ()

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> "CaseCatalog":
        duplicates = _duplicates([case.case_id for case in self.cases])
        if duplicates:
            raise ValueError(
                "duplicate case_id value(s): " + ", ".join(duplicates)
            )
        duplicate_resources = _duplicates(
            [resource.resource_id for resource in self.resources]
        )
        if duplicate_resources:
            raise ValueError(
                "duplicate resource_id value(s): "
                + ", ".join(duplicate_resources)
            )
        known_resources = {resource.resource_id for resource in self.resources}
        for case in self.cases:
            unknown = [
                reference
                for reference in case.resource_refs
                if reference not in known_resources
            ]
            if unknown:
                raise ValueError(
                    f"case {case.case_id!r} references unknown resource_id: "
                    f"{unknown[0]!r}"
                )
        return self

    def get(self, case_id: str) -> CaseDefinition:
        """Return one case by stable ID or raise a clear lookup error."""
        for case in self.cases:
            if case.case_id == case_id:
                return case
        raise KeyError(f"unknown case_id: {case_id!r}")

    def resources_for_case(
        self, case_id: str
    ) -> tuple[CaseResourceDefinition, ...]:
        """Resolve one case's explicit resource references in declared order."""
        case = self.get(case_id)
        by_id = {resource.resource_id: resource for resource in self.resources}
        return tuple(by_id[reference] for reference in case.resource_refs)


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

    resources_path = directory.parent / "resources.yaml"
    resources: tuple[CaseResourceDefinition, ...] = ()
    if resources_path.is_file():
        try:
            raw_resources = yaml.safe_load(
                resources_path.read_text(encoding="utf-8")
            )
        except OSError as error:
            raise OSError(
                f"could not read case resource catalogue {resources_path}: {error}"
            ) from error
        except yaml.YAMLError as error:
            raise ValueError(
                f"invalid YAML in case resource catalogue {resources_path}: {error}"
            ) from error
        if not isinstance(raw_resources, dict):
            raise ValueError(
                f"case resource catalogue {resources_path} must contain a mapping"
            )
        try:
            resources = tuple(
                CaseResourceDefinition.model_validate(item)
                for item in raw_resources.get("resources", ())
            )
        except (TypeError, ValidationError) as error:
            raise ValueError(
                f"invalid case resource catalogue {resources_path}: {error}"
            ) from error
    try:
        return CaseCatalog(cases=tuple(cases), resources=resources)
    except ValidationError as error:
        raise ValueError(f"invalid case catalogue {directory}: {error}") from error
