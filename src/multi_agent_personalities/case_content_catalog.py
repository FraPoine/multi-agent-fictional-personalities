"""Validated, spoiler-free playable content for local investigation cases."""

from pathlib import Path
from typing import Annotated, Literal
import json

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

from multi_agent_personalities.case_catalog import CaseCatalog, normalize_case_lead_reference


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*$", strict=True)]


class ContentGate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    requires_all_flags: tuple[Key, ...] = ()
    requires_any_flags: tuple[Key, ...] = ()
    forbids_flags: tuple[Key, ...] = ()
    requires_items: tuple[Key, ...] = ()
    requires_interactions: tuple[Key, ...] = ()
    requires_choices: dict[Key, tuple[Key, ...]] = {}
    failure_behavior: Literal["stop_lead", "stop_lead_revisitable"] | None = None
    failure_texts: dict[str, str] = {}


class ContentSource(BaseModel):
    """Auditable pointer back to the supplied source document."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    document: NonEmptyStr
    page: int | None = Field(default=None, ge=1)
    pages: tuple[int, ...] = ()
    region: NonEmptyStr


class ContentEffect(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["set_flag", "grant_item", "increase_lead_budget", "close_lead_after_reveal", "close_scope_after_reveal", "end_case"]
    flag_id: Key | None = None
    item_id: Key | None = None
    amount: int | None = None
    scope: Key | None = None
    outcome: Key | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "ContentEffect":
        required = {
            "set_flag": "flag_id", "grant_item": "item_id",
            "increase_lead_budget": "amount", "close_scope_after_reveal": "scope",
            "end_case": "outcome",
        }.get(self.type)
        if required is not None and getattr(self, required) is None:
            raise ValueError(f"{self.type} requires {required}")
        return self


class InteractionOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    option_id: Key
    label_texts: dict[str, NonEmptyStr]


class ContentInteraction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["confirmation", "single_choice"]
    interaction_id: Key
    prompt_texts: dict[str, NonEmptyStr]
    options: tuple[InteractionOption, ...] = ()
    required_before_reveal: bool

    @model_validator(mode="after")
    def validate_options(self) -> "ContentInteraction":
        ids = [item.option_id for item in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate interaction option_id")
        if self.type == "single_choice" and not ids:
            raise ValueError("single_choice interaction requires options")
        if self.type == "confirmation" and ids:
            raise ValueError("confirmation interaction cannot declare options")
        return self


class ContentSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    section_id: Key
    order: int = Field(ge=1)
    texts: dict[str, NonEmptyStr]
    gate: ContentGate = ContentGate()
    effects: tuple[ContentEffect, ...] = ()
    interaction: ContentInteraction | None = None
    return_policy_after_reveal: Literal["unchanged", "top_floor_closed", "closed_after_reveal"]
    lead_cost: int = Field(default=0, ge=0)
    scope_id: Key | None = None


class ContentVariant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    variant_id: Key
    mode: Key
    lead_cost: int = Field(default=0, ge=0)
    source: ContentSource | None = None
    sections: tuple[ContentSection, ...]


class ContentLead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    case_id: Key
    lead_key: Key
    reference: NonEmptyStr
    reference_scheme: NonEmptyStr
    source: ContentSource
    requires_app_extension: bool = False
    sections: tuple[ContentSection, ...] = ()
    variants: tuple[ContentVariant, ...] = ()

    @model_validator(mode="after")
    def validate_shape(self) -> "ContentLead":
        if bool(self.sections) == bool(self.variants):
            raise ValueError("lead requires exactly one of sections or variants")
        canonical = normalize_case_lead_reference(self.reference_scheme, self.reference)
        if canonical != self.reference:
            raise ValueError(f"reference must use canonical form {canonical!r}")
        return self

    def sections_for_mode(self, mode: str | None) -> tuple[ContentSection, ...]:
        if self.sections:
            if mode is not None:
                raise ValueError("mode is not supported by this lead")
            return self.sections
        if mode is None:
            raise ValueError("mode is required for this lead")
        for variant in self.variants:
            if variant.mode == mode:
                return variant.sections
        raise ValueError(f"mode {mode!r} is unavailable for lead {self.reference!r}")


class FlagDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    flag_id: Key
    initial: bool


class ItemDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    item_id: Key
    initial: bool


class ChoiceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    choice_id: Key
    scope: Key
    options: tuple[Key, ...]


class ScopeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scope_id: Key
    initially_available: bool


class StateInteractionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    interaction_id: Key
    scope: Key
    type: Literal["confirmation"]
    initial: Literal["unconfirmed"]


class LeadBudgetDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    initial: int = Field(ge=0)


class DerivedReferenceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    requires_item: Key
    mappings: dict[NonEmptyStr, NonEmptyStr]


class InterventionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    available_after_lead_budget: bool
    exactly_one_entry: bool
    ends_case: bool


class StateDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    case_id: Key
    flags: tuple[FlagDefinition, ...] = ()
    choices: tuple[ChoiceDefinition, ...] = ()
    interactions: tuple[StateInteractionDefinition, ...] = ()
    scopes: tuple[ScopeDefinition, ...] = ()
    items: tuple[ItemDefinition, ...] = ()
    lead_budget: LeadBudgetDefinition | None = None
    modes: tuple[Key, ...] = ()
    derived_references: tuple[DerivedReferenceDefinition, ...] = ()
    intervention: InterventionDefinition | None = None
    lead_accounting: Literal["section_once", "first_visit", "variant_visit"]
    revisit_charging: Literal["uncharged", "configured_variant"]


class CaseContentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: Key
    leads: tuple[ContentLead, ...]
    state: StateDefinition

    @model_validator(mode="after")
    def validate_graph(self) -> "CaseContentDefinition":
        if self.state.case_id != self.case_id or any(x.case_id != self.case_id for x in self.leads):
            raise ValueError("cross-file case_id mismatch")
        lead_keys = [x.lead_key for x in self.leads]
        section_groups = [s for lead in self.leads for s in (lead.sections or tuple(y for v in lead.variants for y in v.sections))]
        section_ids = [x.section_id for x in section_groups]
        if len(lead_keys) != len(set(lead_keys)): raise ValueError("duplicate lead_key")
        if len(section_ids) != len(set(section_ids)): raise ValueError("duplicate section_id")
        if any(x.scope not in set(lead_keys) for x in (*self.state.choices, *self.state.interactions)):
            raise ValueError("choice or interaction scope must reference a lead_key")
        flags = {x.flag_id for x in self.state.flags}; items = {x.item_id for x in self.state.items}
        choices = {x.choice_id: set(x.options) for x in self.state.choices}
        scopes = {x.scope_id for x in self.state.scopes}
        governed_scopes: set[str] = set()
        interactions = {x.interaction_id for x in self.state.interactions}
        for section in section_groups:
            if section.scope_id:
                if section.scope_id not in scopes: raise ValueError("dangling scope reference")
                governed_scopes.add(section.scope_id)
            if section.interaction:
                interactions.add(section.interaction.interaction_id)
                if section.interaction.type == "single_choice":
                    choices.setdefault(section.interaction.interaction_id, {x.option_id for x in section.interaction.options})
            referenced_flags = {*section.gate.requires_all_flags, *section.gate.requires_any_flags, *section.gate.forbids_flags}
            if not referenced_flags <= flags: raise ValueError("dangling flag reference")
            if not set(section.gate.requires_items) <= items: raise ValueError("dangling item reference")
            if not set(section.gate.requires_interactions) <= interactions: raise ValueError("dangling interaction reference")
            for choice_id, options in section.gate.requires_choices.items():
                if choice_id not in choices or not set(options) <= choices[choice_id]: raise ValueError("dangling choice reference")
            for effect in section.effects:
                if effect.flag_id and effect.flag_id not in flags: raise ValueError("dangling flag reference")
                if effect.item_id and effect.item_id not in items: raise ValueError("dangling item reference")
                if effect.scope and effect.scope not in scopes: raise ValueError("dangling scope reference")
        closure_scopes = {effect.scope for section in section_groups for effect in section.effects if effect.type == "close_scope_after_reveal"}
        if not closure_scopes <= governed_scopes: raise ValueError("closure scope has no governed runtime node")
        for derived in self.state.derived_references:
            if derived.requires_item not in items: raise ValueError("dangling item reference")
            for target in derived.mappings.values():
                matching = [lead for lead in self.leads if lead.reference == target]
                if not matching or not any(derived.requires_item in section.gate.requires_items for lead in matching for section in (lead.sections or tuple(s for v in lead.variants for s in v.sections))):
                    raise ValueError("derived reference target must be governed by its required item")
        declared_modes = set(self.state.modes)
        used_modes = {variant.mode for lead in self.leads for variant in lead.variants}
        if declared_modes != used_modes:
            raise ValueError("declared modes must match lead variants")
        if self.state.lead_accounting == "variant_visit" and self.state.lead_budget is None:
            raise ValueError("variant_visit accounting requires a lead budget")
        if self.state.lead_accounting != "variant_visit" and any(variant.lead_cost for lead in self.leads for variant in lead.variants):
            raise ValueError("variant lead costs require variant_visit accounting")
        return self

    @property
    def authored(self) -> bool:
        return True

    def supported_modes(self, lead_key: str) -> tuple[str, ...]:
        lead = self.lead(lead_key)
        return tuple(variant.mode for variant in lead.variants)

    def lead(self, lead_key: str) -> ContentLead:
        for lead in self.leads:
            if lead.lead_key == lead_key: return lead
        raise KeyError(lead_key)


class CaseContentCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cases: tuple[CaseContentDefinition, ...]

    @model_validator(mode="after")
    def unique_cases(self) -> "CaseContentCatalog":
        ids = [x.case_id for x in self.cases]
        if len(ids) != len(set(ids)): raise ValueError("duplicate case_id")
        return self

    def get(self, case_id: str) -> CaseContentDefinition | None:
        return next((x for x in self.cases if x.case_id == case_id), None)


def default_case_content_directory(project_root: Path) -> Path:
    return Path(project_root).resolve() / "configs" / "investigation" / "content"


def load_case_content_catalog(directory: Path, case_catalog: CaseCatalog | None = None) -> CaseContentCatalog:
    """Load only playable files; questions and spoiler material are never opened."""
    root = Path(directory).resolve()
    cases = []
    for case_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        try:
            state = StateDefinition.model_validate_json((case_dir / "state.json").read_text(encoding="utf-8"))
            leads = tuple(ContentLead.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted((case_dir / "leads").glob("*.json")))
            content = CaseContentDefinition(case_id=case_dir.name, leads=leads, state=state)
        except (OSError, ValidationError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid case content {case_dir}: {error}") from error
        if case_catalog is not None:
            structural = case_catalog.get(content.case_id)
            by_key = {x.lead_key: x for x in structural.leads}
            if set(by_key) != {x.lead_key for x in content.leads}: raise ValueError(f"case {content.case_id!r} structural/content lead mismatch")
            for lead in content.leads:
                expected = by_key[lead.lead_key]
                if (lead.reference, lead.reference_scheme) != (expected.reference, expected.reference_scheme): raise ValueError(f"case {content.case_id!r} lead {lead.lead_key!r} structural/content mismatch")
        cases.append(content)
    try:
        return CaseContentCatalog(cases=tuple(cases))
    except ValidationError as error:
        raise ValueError(f"invalid case content catalogue: {error}") from error
