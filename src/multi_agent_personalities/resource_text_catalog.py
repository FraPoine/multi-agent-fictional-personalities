"""Strict public transcriptions for explicitly consulted local case resources."""

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

from multi_agent_personalities.case_catalog import CaseCatalog, CaseResourceType


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$", strict=True)]


class ResourceTextSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document: NonEmptyStr
    page: int = Field(strict=True, ge=1)
    region: NonEmptyStr


class VerifiedResourceTextBlock(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    entry_id: Key
    order: int = Field(strict=True, ge=1)
    texts: dict[Literal["en"], NonEmptyStr]


class ResourceTextDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    case_id: Key
    resource_id: Key
    resource_type: CaseResourceType
    source: ResourceTextSource
    source_asset_path: Path
    transcription_kind: Literal["verified_transcription", "player_only_image"]
    agent_readable: bool
    entries: tuple[VerifiedResourceTextBlock, ...] = ()

    @model_validator(mode="after")
    def validate_payload(self) -> "ResourceTextDefinition":
        path = self.source_asset_path
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("source_asset_path must be a safe local relative path")
        ids = [entry.entry_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate resource text entry_id")
        if [entry.order for entry in self.entries] != list(range(1, len(self.entries) + 1)):
            raise ValueError("resource text entry order must be contiguous")
        if self.agent_readable:
            if self.transcription_kind != "verified_transcription" or not self.entries:
                raise ValueError("agent-readable resources require verified text")
        elif self.transcription_kind != "player_only_image" or self.entries:
            raise ValueError("player-only resources cannot contain agent-readable text")
        return self

    def render(self) -> str:
        if not self.agent_readable:
            raise ValueError("player-only resource text cannot be rendered")
        return "\n\n".join(entry.texts["en"] for entry in self.entries)


class CaseOperationalGuidance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: Key
    entries: tuple[VerifiedResourceTextBlock, ...]

    @model_validator(mode="after")
    def validate_entries(self) -> "CaseOperationalGuidance":
        ids = [entry.entry_id for entry in self.entries]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("operational guidance requires unique entries")
        if [entry.order for entry in self.entries] != list(range(1, len(self.entries) + 1)):
            raise ValueError("operational guidance order must be contiguous")
        return self


class OperationalGuidanceCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    cases: tuple[CaseOperationalGuidance, ...]


class ResourceTextCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    resources: tuple[ResourceTextDefinition, ...]
    guidance: tuple[CaseOperationalGuidance, ...] = ()

    @model_validator(mode="after")
    def validate_unique_resources(self) -> "ResourceTextCatalog":
        ids = [resource.resource_id for resource in self.resources]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate resource text resource_id")
        case_ids = [case.case_id for case in self.guidance]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("duplicate operational guidance case_id")
        return self

    def get(self, case_id: str, resource_id: str) -> ResourceTextDefinition:
        for resource in self.resources:
            if resource.case_id == case_id and resource.resource_id == resource_id:
                return resource
        if any(resource.resource_id == resource_id for resource in self.resources):
            raise ResourceTextOwnershipError("resource belongs to another case")
        raise UnknownResourceTextError(f"unknown resource text: {resource_id!r}")


class UnknownResourceTextError(LookupError):
    """Raised when no verified public resource definition exists."""


class ResourceTextOwnershipError(ValueError):
    """Raised when a resource is requested through the wrong case."""


def default_resource_text_directory(project_root: Path) -> Path:
    return Path(project_root).resolve() / "configs" / "investigation" / "resources_text"


def load_resource_text_catalog(directory: Path, case_catalog: CaseCatalog, *, asset_root: Path | None = None) -> ResourceTextCatalog:
    """Load public resource text without opening any private conclusion path."""
    root = Path(directory).resolve()
    resolved_asset_root = (root.parent if asset_root is None else Path(asset_root)).resolve()
    definitions: list[ResourceTextDefinition] = []
    try:
        for case_directory in sorted(path for path in root.iterdir() if path.is_dir()):
            files = sorted(case_directory.glob("*.json"))
            if not files:
                raise ValueError(f"resource text case directory is empty: {case_directory.name!r}")
            for path in files:
                definition = ResourceTextDefinition.model_validate_json(path.read_text(encoding="utf-8"))
                if definition.case_id != case_directory.name:
                    raise ValueError("resource text definition has cross-directory case_id")
                case = case_catalog.get(definition.case_id)
                resources = {resource.resource_id: resource for resource in case_catalog.resources_for_case(case.case_id)}
                if definition.resource_id not in resources:
                    raise ValueError("resource text definition is orphaned or belongs to another case")
                structural = resources[definition.resource_id]
                if definition.resource_type is not structural.type:
                    raise ValueError("resource text type does not match resource catalogue")
                if structural.asset_path is None or definition.source_asset_path != structural.asset_path:
                    raise ValueError("resource text source asset does not match resource catalogue")
                asset = (resolved_asset_root / definition.source_asset_path).resolve()
                if resolved_asset_root not in asset.parents or not asset.is_file():
                    raise ValueError("resource text source asset is missing or unsafe")
                definitions.append(definition)
        guidance_path = root / "guidance.json"
        guidance = OperationalGuidanceCatalog.model_validate_json(guidance_path.read_text(encoding="utf-8"))
        known_case_ids = {case.case_id for case in case_catalog.cases}
        if not {case.case_id for case in guidance.cases} <= known_case_ids:
            raise ValueError("operational guidance references unknown case_id")
        by_case: dict[str, set[str]] = {}
        for definition in definitions:
            by_case.setdefault(definition.case_id, set()).add(definition.resource_id)
        guidance_case_ids = {case.case_id for case in guidance.cases}
        if set(by_case) != guidance_case_ids:
            raise ValueError("resource-definition and operational-guidance case IDs must agree")
        for case_id, defined_ids in by_case.items():
            expected_ids = {resource.resource_id for resource in case_catalog.resources_for_case(case_id)}
            if defined_ids != expected_ids:
                raise ValueError(f"resource text definitions are missing for case {case_id!r}")
        catalog = ResourceTextCatalog(resources=tuple(definitions), guidance=guidance.cases)
    except (OSError, KeyError, ValidationError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid resource text catalogue: {error}") from error
    return catalog
