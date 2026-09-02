"""Stateless application operations for Lead/Visit investigations."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from multi_agent_personalities.case_catalog import (
    CaseDefinition,
    CaseLeadDefinition,
    parse_supported_case_lead_reference,
)
from multi_agent_personalities.case_content_catalog import (
    CaseContentDefinition,
    ContentEffect,
    ContentInteraction,
    ContentSection,
)

from multi_agent_personalities.application.investigation_prompts import (
    InvestigationPromptName,
    load_investigation_prompt,
    render_decisions,
    render_hypotheses,
    render_investigation_prompt,
)
from multi_agent_personalities.application.investigation_structured_output import (
    GeneratedFinalTheoryPayload,
    StructuredGenerationResult,
    parse_structured_generation,
)
from multi_agent_personalities.application.investigation_tasks import (
    investigation_lead_discussion_task_name,
    investigation_lead_final_theory_task_name,
)
from multi_agent_personalities.agent_runtime import generate_reply

from multi_agent_personalities.application.investigation_ids import (
    DeterministicInvestigationIdFactory,
)
from multi_agent_personalities.models import (
    AgentAnalysis,
    ConversationRun,
    EvidenceReference,
    FinalTheory,
    GroupDecision,
    GroupDecisionType,
    Hypothesis,
    HypothesisStatus,
    InvestigationLead,
    InvestigationSession,
    InvestigationStatus,
    LeadVisit,
    Message,
    RevealedInformation,
    CaseChoiceState,
    CasePlayState,
    ConclusionMode,
    LeadAccountingEntry,
)
from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.simulation import (
    RoundRobinSelector,
    SpeakerSelector,
    simulate_chat,
)
from multi_agent_personalities.simulation.participant import (
    ConversationParticipant,
)


MAX_LEAD_DISCUSSION_TURNS = 100


def create_session(
    *,
    id_factory: DeterministicInvestigationIdFactory,
    introduction: str,
    participant_ids: Sequence[str],
    case_id: str = "legacy-local-demo",
    case_content: CaseContentDefinition | None = None,
    conclusion_mode: ConclusionMode = ConclusionMode.GENERATED_FINAL_THEORY,
) -> InvestigationSession:
    """Create one active investigation with an empty Lead/Visit graph."""
    if not isinstance(id_factory, DeterministicInvestigationIdFactory):
        raise ValueError(
            "id_factory must be a DeterministicInvestigationIdFactory"
        )
    if not isinstance(introduction, str) or not introduction.strip():
        raise ValueError("introduction must not be empty")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must not be empty")
    if isinstance(participant_ids, (str, bytes)) or not isinstance(
        participant_ids, Sequence
    ):
        raise ValueError("participant_ids must be a sequence of identifiers")
    # Prove the namespace can produce every authoritative first child ID.
    id_factory.lead_id(1)
    id_factory.visit_id(1)
    id_factory.information_id(0)
    id_factory.discussion_segment_id(1, 1)
    if case_content is not None and case_content.case_id != case_id:
        raise ValueError("case_content must match case_id")
    state = None
    if case_content is not None:
        state = CasePlayState(
            flags=tuple(x.flag_id for x in case_content.state.flags if x.initial),
            items=tuple(x.item_id for x in case_content.state.items if x.initial),
            closed_scopes=tuple(x.scope_id for x in case_content.state.scopes if not x.initially_available),
            lead_budget_remaining=(case_content.state.lead_budget.initial if case_content.state.lead_budget else None),
        )
    return InvestigationSession(
        session_id=id_factory.session_id,
        case_id=case_id,
        case_introduction=introduction,
        participant_ids=tuple(participant_ids),
        status=InvestigationStatus.ACTIVE,
        conclusion_mode=conclusion_mode,
        case_state=state,
    )


@dataclass(frozen=True)
class LeadDiscussionResult:
    """One atomic session update and its bounded discussion segment."""

    session: InvestigationSession
    conversation_run: ConversationRun
    context: str


@dataclass(frozen=True)
class LeadFinalizationResult:
    """One atomic Lead/Visit completion and its generation provenance."""

    session: InvestigationSession
    final_theory: FinalTheory
    generation: StructuredGenerationResult[GeneratedFinalTheoryPayload]


class InvalidCaseLeadReferenceError(ValueError):
    """Raised when input matches none of the case's structural schemes."""


class UnknownCaseLeadReferenceError(LookupError):
    """Raised when valid structural input is absent from the selected case."""


class CurrentCaseLeadConflictError(ValueError):
    """Raised when the resolved semantic lead is already current."""


class GameplayConflictError(ValueError):
    """Base error for a structurally valid but unavailable gameplay action."""


class InvalidGameplayModeError(GameplayConflictError):
    """Raised when a lead does not support the selected mode."""


class LockedGameplayNodeError(GameplayConflictError):
    """Raised when authored prerequisites do not permit a gameplay node."""


class ClosedGameplayNodeError(GameplayConflictError):
    """Raised when an irreversible authored closure blocks future play."""


class GameplayBudgetError(GameplayConflictError):
    """Raised when a valid action cannot be afforded or selected yet."""


class ManualRevealForbiddenError(GameplayConflictError):
    """Raised when direct Game Master injection targets an authored case."""


@dataclass(frozen=True)
class CaseLeadVisitResult:
    """Case-aware resolution with an optional newly created visit."""

    session: InvestigationSession
    lead: InvestigationLead
    created: bool


def resolve_case_lead(
    case_definition: CaseDefinition, raw_reference: str
) -> CaseLeadDefinition:
    """Resolve player input against the selected case's declared schemes."""
    if not isinstance(case_definition, CaseDefinition):
        raise ValueError("case_definition must be a validated CaseDefinition")
    try:
        parsed = parse_supported_case_lead_reference(raw_reference)
    except ValueError as error:
        raise InvalidCaseLeadReferenceError(str(error)) from error
    for lead in case_definition.leads:
        if (
            lead.reference_scheme == parsed.reference_scheme
            and lead.reference == parsed.canonical_reference
        ):
            return lead
    raise UnknownCaseLeadReferenceError(
        f"unknown lead reference for case {case_definition.case_id!r}"
    )


def visit_case_lead(
    session: InvestigationSession,
    *,
    case_definition: CaseDefinition,
    raw_reference: str,
    id_factory: DeterministicInvestigationIdFactory,
) -> CaseLeadVisitResult:
    """Resolve and first-visit a case lead without implicit revisits."""
    snapshot = _validated_snapshot(session, id_factory)
    if snapshot.case_id != case_definition.case_id:
        raise ValueError("case_definition must match the session case_id")
    definition = resolve_case_lead(case_definition, raw_reference)
    existing = next(
        (
            lead
            for lead in snapshot.leads
            if lead.case_lead_key == definition.lead_key
        ),
        None,
    )
    if existing is not None:
        if snapshot.visits and snapshot.visits[-1].lead_id == existing.lead_id:
            raise CurrentCaseLeadConflictError("case lead is already current")
        return CaseLeadVisitResult(snapshot, existing, False)
    updated = visit_lead(
        snapshot,
        id_factory=id_factory,
        label=definition.label,
        kind=definition.kind,
        case_lead_key=definition.lead_key,
        reference=definition.reference,
    )
    return CaseLeadVisitResult(updated, updated.leads[-1], True)


@dataclass(frozen=True)
class _LeadDiscussionReplyGenerator:
    visit_index: int
    segment_index: int

    def __call__(
        self,
        *,
        participant: ConversationParticipant,
        history: tuple[Message, ...],
        topic: str,
        run_id: str,
        turn_index: int,
        timestamp: datetime,
    ) -> Message:
        return generate_reply(
            persona=participant.persona,
            history=history,
            topic=topic,
            run_id=run_id,
            turn_index=turn_index,
            provider=participant.provider,
            provider_name=participant.provider_name,
            model_name=participant.model_name,
            timestamp=timestamp,
            task_name=investigation_lead_discussion_task_name(
                participant.character_id,
                self.visit_index,
                self.segment_index,
                turn_index,
            ),
        )


def _validated_snapshot(
    session: InvestigationSession,
    id_factory: DeterministicInvestigationIdFactory,
) -> InvestigationSession:
    if not isinstance(session, InvestigationSession):
        raise ValueError("session must be a validated InvestigationSession")
    snapshot = InvestigationSession.model_validate(
        session.model_dump(mode="python")
    )
    if snapshot.status is not InvestigationStatus.ACTIVE:
        raise ValueError("lead operations require an active session")
    if not isinstance(id_factory, DeterministicInvestigationIdFactory):
        raise ValueError(
            "id_factory must be a DeterministicInvestigationIdFactory"
        )
    if id_factory.session_id != snapshot.session_id:
        raise ValueError("id_factory session_id must match the investigation session")
    return snapshot


def _visit_by_id(session: InvestigationSession, visit_id: str) -> LeadVisit:
    if not isinstance(visit_id, str) or not visit_id.strip():
        raise ValueError("visit_id must not be empty")
    for visit in session.visits:
        if visit.visit_id == visit_id:
            return visit
    raise ValueError(f"unknown visit_id: {visit_id!r}")


def _require_current_visit(
    session: InvestigationSession, visit_id: str
) -> LeadVisit:
    """Reject chronological writes to a visit superseded by a later visit."""
    visit = _visit_by_id(session, visit_id)
    if not session.visits or session.visits[-1].visit_id != visit.visit_id:
        raise ValueError(
            "new investigation activity must target the current latest visit"
        )
    return visit


def _lead_by_id(
    session: InvestigationSession, lead_id: str
) -> InvestigationLead:
    if not isinstance(lead_id, str) or not lead_id.strip():
        raise ValueError("lead_id must not be empty")
    for lead in session.leads:
        if lead.lead_id == lead_id:
            return lead
    raise ValueError(f"unknown lead_id: {lead_id!r}")


def visit_lead(
    session: InvestigationSession,
    *,
    id_factory: DeterministicInvestigationIdFactory,
    lead_id: str | None = None,
    label: str | None = None,
    kind: str | None = None,
    case_lead_key: str | None = None,
    reference: str | None = None,
    mode: str | None = None,
) -> InvestigationSession:
    """Visit a new semantic lead or revisit an existing lead."""
    snapshot = _validated_snapshot(session, id_factory)
    if lead_id is None:
        if not isinstance(label, str) or not label.strip():
            raise ValueError("label is required when creating a new lead")
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("kind is required when creating a new lead")
        resolved_lead = InvestigationLead(
            lead_id=id_factory.lead_id(len(snapshot.leads) + 1),
            session_id=snapshot.session_id,
            case_lead_key=case_lead_key,
            reference=reference,
            label=label,
            kind=kind,
        )
        updated_leads = (*snapshot.leads, resolved_lead)
    else:
        if any(item is not None for item in (label, kind, case_lead_key, reference)):
            raise ValueError("lead definition fields must be omitted when revisiting")
        resolved_lead = _lead_by_id(snapshot, lead_id)
        updated_leads = snapshot.leads

    visit_index = len(snapshot.visits) + 1
    resolved_visit_id = id_factory.visit_id(visit_index)
    if any(item.visit_id == resolved_visit_id for item in snapshot.visits):
        raise ValueError(f"duplicate visit_id: {resolved_visit_id!r}")
    new_visit = LeadVisit(
        visit_id=resolved_visit_id,
        session_id=snapshot.session_id,
        lead_id=resolved_lead.lead_id,
        visit_index=visit_index,
        mode=mode,
    )
    payload = snapshot.model_dump(mode="python")
    payload.update(leads=updated_leads, visits=(*snapshot.visits, new_visit))
    return InvestigationSession.model_validate(payload)


def _state_payload(session: InvestigationSession) -> dict:
    if session.case_state is None:
        raise ValueError("case has no playable content state")
    return session.case_state.model_dump(mode="python")


def supported_case_lead_modes(case_content: CaseContentDefinition, lead_key: str) -> tuple[str, ...]:
    """Return the deterministic authored modes for one semantic lead."""
    try:
        return case_content.supported_modes(lead_key)
    except KeyError as error:
        raise UnknownCaseLeadReferenceError(f"unknown case lead_key: {lead_key!r}") from error


def _append_accounting(payload: dict, entry: LeadAccountingEntry) -> None:
    payload["accounting_entries"] = (*payload["accounting_entries"], entry)


def _section_gate_passes(section: ContentSection, state: CasePlayState) -> bool:
    flags, items = set(state.flags), set(state.items)
    choices = {x.choice_id: x.option_id for x in state.choices}
    gate = section.gate
    return (
        set(gate.requires_all_flags) <= flags
        and (not gate.requires_any_flags or bool(set(gate.requires_any_flags) & flags))
        and not (set(gate.forbids_flags) & flags)
        and set(gate.requires_items) <= items
        and set(gate.requires_interactions) <= set(state.completed_interactions)
        and all(choices.get(key) in options for key, options in gate.requires_choices.items())
    )


def _apply_effect(payload: dict, effect: ContentEffect, lead_key: str, lead_id: str, visit_id: str, section_id: str) -> None:
    def add(field: str, value: str) -> None:
        payload[field] = (*payload[field], value) if value not in payload[field] else payload[field]
    if effect.type == "set_flag": add("flags", effect.flag_id)  # type: ignore[arg-type]
    elif effect.type == "grant_item": add("items", effect.item_id)  # type: ignore[arg-type]
    elif effect.type == "increase_lead_budget":
        if payload["lead_budget_remaining"] is None: raise ValueError("lead budget effect without declared budget")
        payload["lead_budget_remaining"] += effect.amount
        _append_accounting(payload, LeadAccountingEntry(source_kind="budget-adjustment", source_id=section_id, lead_id=lead_id, visit_id=visit_id, amount=-effect.amount, uniqueness="once-per-section"))
    elif effect.type == "close_lead_after_reveal": add("closed_lead_keys", lead_key)
    elif effect.type == "close_scope_after_reveal": add("closed_scopes", effect.scope)  # type: ignore[arg-type]
    elif effect.type == "end_case": payload["outcome"] = effect.outcome


def _mode_sections(content_lead, mode: str | None) -> tuple[ContentSection, ...]:
    try:
        return content_lead.sections_for_mode(mode)
    except ValueError as error:
        raise InvalidGameplayModeError(str(error)) from error


def _preflight_sections(sections: tuple[ContentSection, ...], state: CasePlayState, *, allow_fully_disclosed: bool = False) -> None:
    """Require at least one reachable, open, not-yet-applied authored node."""
    has_unapplied = False
    for section in sections:
        if section.section_id in state.applied_section_ids:
            continue
        has_unapplied = True
        if not _section_gate_passes(section, state):
            if section.gate.failure_behavior:
                raise LockedGameplayNodeError(f"section {section.section_id!r} prerequisites are not satisfied")
            continue
        if section.scope_id and section.scope_id in state.closed_scopes:
            raise ClosedGameplayNodeError(f"scope {section.scope_id!r} is closed")
        return
    if allow_fully_disclosed and not has_unapplied:
        return
    raise LockedGameplayNodeError("no authored content is currently available")


def _variant_preflight(content_lead, mode: str | None, state: CasePlayState, *, allow_fully_disclosed: bool = False):
    sections = _mode_sections(content_lead, mode)
    _preflight_sections(sections, state, allow_fully_disclosed=allow_fully_disclosed)
    if not content_lead.variants:
        return None
    variant = next(item for item in content_lead.variants if item.mode == mode)
    remaining = state.lead_budget_remaining
    if variant.mode == "intervention" and remaining is not None and remaining > 0:
        raise GameplayBudgetError("intervention is not available while lead budget remains")
    if remaining is not None and variant.lead_cost > remaining:
        raise GameplayBudgetError("lead budget is exhausted")
    return variant


def disclose_case_sections(
    session: InvestigationSession, *, case_content: CaseContentDefinition,
    visit_id: str, id_factory: DeterministicInvestigationIdFactory,
) -> InvestigationSession:
    """Reveal currently eligible static sections and apply each effect once."""
    snapshot = _validated_snapshot(session, id_factory)
    visit = _require_current_visit(snapshot, visit_id)
    lead = _lead_by_id(snapshot, visit.lead_id)
    if lead.case_lead_key is None: return snapshot
    content_lead = case_content.lead(lead.case_lead_key)
    sections = content_lead.sections_for_mode(visit.mode)
    state = snapshot.case_state
    if state is None: raise ValueError("case content requires initialized state")
    already = {x.source_id for x in snapshot.revealed_information if x.source_kind == "case-section"}
    for section in sections:
        if section.section_id in already or section.section_id in state.applied_section_ids:
            continue
        if section.scope_id and section.scope_id in state.closed_scopes:
            break
        if not _section_gate_passes(section, state):
            failure = section.gate.failure_texts.get("en")
            failure_id = f"{section.section_id}-gate"
            known = {x.source_id for x in snapshot.revealed_information if x.source_kind == "case-gate"}
            if failure and failure_id not in known:
                snapshot = reveal_information(snapshot, visit_id=visit_id, information_texts=(failure,), id_factory=id_factory, source_kind="case-gate", source_ids=(failure_id,))
            if section.gate.failure_behavior:
                break
            continue
        interaction = section.interaction
        if interaction is not None and interaction.required_before_reveal:
            completed = interaction.interaction_id in state.completed_interactions
            chosen = interaction.interaction_id in {x.choice_id for x in state.choices}
            if not completed and not chosen: break
        text = section.texts.get("en")
        if text:
            snapshot = reveal_information(snapshot, visit_id=visit_id, information_texts=(text,), id_factory=id_factory, source_kind="case-section", source_ids=(section.section_id,))
        payload = _state_payload(snapshot)
        if section.lead_cost:
            _append_accounting(payload, LeadAccountingEntry(source_kind="section-cost", source_id=section.section_id, lead_id=lead.lead_id, visit_id=visit.visit_id, amount=section.lead_cost, uniqueness="once-per-section"))
        for effect in section.effects: _apply_effect(payload, effect, lead.case_lead_key, lead.lead_id, visit.visit_id, section.section_id)
        payload["applied_section_ids"] = (*payload["applied_section_ids"], section.section_id)
        session_payload = snapshot.model_dump(mode="python")
        session_payload["case_state"] = CasePlayState.model_validate(payload)
        if payload["outcome"] is not None:
            session_payload["status"] = InvestigationStatus.COMPLETED
        snapshot = InvestigationSession.model_validate(session_payload)
        state = snapshot.case_state
    return snapshot


def pending_case_interaction(session: InvestigationSession, *, case_content: CaseContentDefinition, visit_id: str) -> ContentInteraction | None:
    visit = _visit_by_id(session, visit_id); lead = _lead_by_id(session, visit.lead_id)
    if lead.case_lead_key is None or session.case_state is None: return None
    state = session.case_state
    for section in case_content.lead(lead.case_lead_key).sections_for_mode(visit.mode):
        if section.section_id in state.applied_section_ids: continue
        if section.scope_id and section.scope_id in state.closed_scopes: return None
        if not _section_gate_passes(section, state):
            if section.gate.failure_behavior: return None
            continue
        if section.interaction and section.interaction.required_before_reveal:
            done = section.interaction.interaction_id in state.completed_interactions or section.interaction.interaction_id in {x.choice_id for x in state.choices}
            if not done: return section.interaction
        return None
    return None


def complete_case_interaction(
    session: InvestigationSession, *, case_content: CaseContentDefinition, visit_id: str,
    interaction_id: str, option_id: str | None, id_factory: DeterministicInvestigationIdFactory,
) -> InvestigationSession:
    snapshot = _validated_snapshot(session, id_factory); _require_current_visit(snapshot, visit_id)
    if snapshot.case_state and snapshot.case_state.outcome: raise ClosedGameplayNodeError("case has ended")
    interaction = pending_case_interaction(snapshot, case_content=case_content, visit_id=visit_id)
    if interaction is None or interaction.interaction_id != interaction_id: raise LockedGameplayNodeError("interaction is not currently available")
    payload = _state_payload(snapshot)
    if interaction.type == "confirmation":
        if option_id not in (None, "confirm"): raise GameplayConflictError("confirmation does not accept a choice")
        payload["completed_interactions"] = (*payload["completed_interactions"], interaction_id)
    else:
        valid = {x.option_id for x in interaction.options}
        if option_id not in valid: raise GameplayConflictError("invalid interaction choice")
        payload["choices"] = (*payload["choices"], CaseChoiceState(choice_id=interaction_id, option_id=option_id))
    session_payload = snapshot.model_dump(mode="python"); session_payload["case_state"] = CasePlayState.model_validate(payload)
    updated = InvestigationSession.model_validate(session_payload)
    return disclose_case_sections(updated, case_content=case_content, visit_id=visit_id, id_factory=id_factory)


def visit_playable_case_lead(
    session: InvestigationSession, *, case_definition: CaseDefinition, case_content: CaseContentDefinition,
    raw_reference: str, mode: str | None, id_factory: DeterministicInvestigationIdFactory,
) -> CaseLeadVisitResult:
    if session.case_id != case_definition.case_id or case_content.case_id != session.case_id:
        raise GameplayConflictError("case definition and content must match the session")
    definition = resolve_case_lead(case_definition, raw_reference)
    state = session.case_state
    if state is None: raise ValueError("playable case state is not initialized")
    if state.outcome: raise ClosedGameplayNodeError("case has ended")
    if definition.lead_key in state.closed_lead_keys: raise ClosedGameplayNodeError("case lead is closed")
    existing = next((x for x in session.leads if x.case_lead_key == definition.lead_key), None)
    if existing is not None: raise CurrentCaseLeadConflictError("revisit this known lead explicitly")
    content_lead = case_content.lead(definition.lead_key)
    variant = _variant_preflight(content_lead, mode, state)
    updated = visit_lead(session, id_factory=id_factory, label=definition.label, kind=definition.kind, case_lead_key=definition.lead_key, reference=definition.reference, mode=mode)
    visit = updated.visits[-1]
    payload = _state_payload(updated)
    if case_content.state.lead_accounting == "first_visit":
        _append_accounting(payload, LeadAccountingEntry(source_kind="first-visit", source_id=definition.lead_key, lead_id=updated.leads[-1].lead_id, visit_id=visit.visit_id, amount=1, uniqueness="once-per-lead"))
    if variant is not None and variant.lead_cost:
        payload["lead_budget_remaining"] -= variant.lead_cost
        _append_accounting(payload, LeadAccountingEntry(source_kind="variant-visit", source_id=variant.variant_id, lead_id=updated.leads[-1].lead_id, visit_id=visit.visit_id, amount=variant.lead_cost, uniqueness="once-per-visit"))
    raw = updated.model_dump(mode="python"); raw["case_state"] = CasePlayState.model_validate(payload); updated = InvestigationSession.model_validate(raw)
    updated = disclose_case_sections(updated, case_content=case_content, visit_id=visit.visit_id, id_factory=id_factory)
    return CaseLeadVisitResult(updated, updated.leads[-1], True)


def revisit_playable_case_lead(
    session: InvestigationSession, *, case_content: CaseContentDefinition,
    lead_id: str, mode: str | None, id_factory: DeterministicInvestigationIdFactory,
) -> InvestigationSession:
    """Create an explicit revisit and disclose information unlocked since last visit."""
    lead = _lead_by_id(session, lead_id)
    if case_content.case_id != session.case_id:
        raise GameplayConflictError("case content must match the session")
    if lead.case_lead_key is None or session.case_state is None: raise ValueError("lead is not backed by playable case content")
    if session.case_state.outcome: raise ClosedGameplayNodeError("case has ended")
    if lead.case_lead_key in session.case_state.closed_lead_keys: raise ClosedGameplayNodeError("case lead is closed")
    content_lead = case_content.lead(lead.case_lead_key)
    variant = _variant_preflight(content_lead, mode, session.case_state, allow_fully_disclosed=(case_content.state.revisit_charging == "uncharged"))
    updated = visit_lead(session, id_factory=id_factory, lead_id=lead_id, mode=mode)
    if variant is not None and variant.lead_cost:
        payload = _state_payload(updated)
        payload["lead_budget_remaining"] -= variant.lead_cost
        _append_accounting(payload, LeadAccountingEntry(source_kind="variant-visit", source_id=variant.variant_id, lead_id=lead.lead_id, visit_id=updated.visits[-1].visit_id, amount=variant.lead_cost, uniqueness="once-per-visit"))
        raw = updated.model_dump(mode="python"); raw["case_state"] = CasePlayState.model_validate(payload); updated = InvestigationSession.model_validate(raw)
    return disclose_case_sections(updated, case_content=case_content, visit_id=updated.visits[-1].visit_id, id_factory=id_factory)


def reveal_information(
    session: InvestigationSession,
    *,
    visit_id: str,
    information_texts: Sequence[str],
    id_factory: DeterministicInvestigationIdFactory,
    source_kind: str | None = None,
    source_ids: Sequence[str] | None = None,
) -> InvestigationSession:
    """Explicitly disclose one or more globally retained information items."""
    snapshot = _validated_snapshot(session, id_factory)
    visit = _require_current_visit(snapshot, visit_id)
    if isinstance(information_texts, (str, bytes)) or not isinstance(
        information_texts, Sequence
    ):
        raise ValueError("information_texts must be a sequence")
    texts = tuple(information_texts)
    if not texts:
        raise ValueError("information_texts must not be empty")
    if any(not isinstance(item, str) or not item.strip() for item in texts):
        raise ValueError("information text must not be empty")
    if source_ids is not None:
        if isinstance(source_ids, (str, bytes)) or not isinstance(
            source_ids, Sequence
        ):
            raise ValueError("source_ids must be a sequence")
        resolved_source_ids: tuple[str | None, ...] = tuple(source_ids)
        if len(resolved_source_ids) != len(texts):
            raise ValueError("source_ids must match information_texts length")
        if source_kind is None:
            raise ValueError("source_kind is required with source_ids")
    else:
        if source_kind is not None:
            raise ValueError("source_ids are required with source_kind")
        resolved_source_ids = (None,) * len(texts)

    start = len(snapshot.revealed_information)
    additions = tuple(
        RevealedInformation(
            information_id=id_factory.information_id(start + offset),
            session_id=snapshot.session_id,
            text=text,
            reveal_index=start + offset,
            lead_id=visit.lead_id,
            visit_id=visit.visit_id,
            source_kind=source_kind,
            source_id=resolved_source_ids[offset],
        )
        for offset, text in enumerate(texts)
    )
    visit_payload = visit.model_dump(mode="python")
    visit_payload["revealed_information_ids"] = (
        *visit.revealed_information_ids,
        *(item.information_id for item in additions),
    )
    updated_visit = LeadVisit.model_validate(visit_payload)
    visits = tuple(
        updated_visit if item.visit_id == visit.visit_id else item
        for item in snapshot.visits
    )
    payload = snapshot.model_dump(mode="python")
    payload.update(
        visits=visits,
        revealed_information=(*snapshot.revealed_information, *additions),
    )
    return InvestigationSession.model_validate(payload)


def reveal_manual_information(
    session: InvestigationSession, *, case_content: CaseContentDefinition | None,
    visit_id: str, information_texts: Sequence[str], id_factory: DeterministicInvestigationIdFactory,
) -> InvestigationSession:
    """Apply the explicit authored/manual capability policy at service level."""
    if case_content is not None and case_content.authored:
        raise ManualRevealForbiddenError("direct information injection is disabled for authored cases")
    return reveal_information(session, visit_id=visit_id, information_texts=information_texts, id_factory=id_factory)


def project_lead_conversation(
    session: InvestigationSession, lead_id: str
) -> tuple[Message, ...]:
    """Project one lead's messages by visit, run, then turn chronology."""
    snapshot = InvestigationSession.model_validate(
        session.model_dump(mode="python")
    )
    _lead_by_id(snapshot, lead_id)
    run_by_id = {item.run_id: item for item in snapshot.conversation_runs}
    messages: list[Message] = []
    for visit in snapshot.visits:
        if visit.lead_id != lead_id:
            continue
        for run_id in visit.conversation_run_ids:
            messages.extend(run_by_id[run_id].messages)
    return tuple(messages)


def build_lead_discussion_context(
    session: InvestigationSession, *, visit_id: str
) -> str:
    """Render deterministic, explicit context from one validated snapshot."""
    snapshot = InvestigationSession.model_validate(
        session.model_dump(mode="python")
    )
    visit = _visit_by_id(snapshot, visit_id)
    lead = _lead_by_id(snapshot, visit.lead_id)
    information_lines = [
        f"{item.reveal_index + 1}. [{item.information_id}] {item.text}"
        for item in snapshot.revealed_information
    ]
    chronology_lines = [
        f"{item.visit_index}. [{item.visit_id}] lead={item.lead_id}"
        for item in snapshot.visits
    ]
    history = project_lead_conversation(snapshot, lead.lead_id)
    history_lines = [
        f"[{item.run_id} turn {item.turn_index}] "
        f"{item.speaker_name}: {item.text}"
        for item in history
    ]
    return "\n\n".join(
        (
            f"Case opening:\n{snapshot.case_introduction}",
            "Current lead:\n"
            f"[{lead.lead_id}] {lead.label} (kind: {lead.kind})\n"
            f"Current visit: [{visit.visit_id}] index {visit.visit_index}",
            "Globally revealed information:\n"
            + ("\n".join(information_lines) or "None."),
            "Investigation chronology:\n"
            + ("\n".join(chronology_lines) or "None."),
            "Previous conversation on this lead:\n"
            + ("\n".join(history_lines) or "None."),
        )
    )


def _ordered_bindings(
    participant_ids: tuple[str, ...],
    participant_bindings: Sequence[ConversationParticipant],
) -> tuple[ConversationParticipant, ...]:
    if isinstance(participant_bindings, (str, bytes)) or not isinstance(
        participant_bindings, Sequence
    ):
        raise ValueError("participant_bindings must be a sequence")
    if any(
        not isinstance(item, ConversationParticipant)
        for item in participant_bindings
    ):
        raise ValueError("every binding must be a ConversationParticipant")
    by_id = {item.character_id: item for item in participant_bindings}
    if len(by_id) != len(participant_bindings) or set(by_id) != set(participant_ids):
        raise ValueError("participant bindings must match session participants")
    return tuple(by_id[item] for item in participant_ids)


def continue_lead_discussion(
    session: InvestigationSession,
    *,
    visit_id: str,
    participant_bindings: Sequence[ConversationParticipant],
    id_factory: DeterministicInvestigationIdFactory,
    turn_count: int,
    selector: SpeakerSelector | None = None,
    seed: int = 42,
    timestamp: datetime | None = None,
) -> LeadDiscussionResult:
    """Generate and atomically attach one bounded lead discussion segment."""
    snapshot = _validated_snapshot(session, id_factory)
    visit = _require_current_visit(snapshot, visit_id)
    if (
        isinstance(turn_count, bool)
        or not isinstance(turn_count, int)
        or not 1 <= turn_count <= MAX_LEAD_DISCUSSION_TURNS
    ):
        raise ValueError(
            "turn_count must be a strict integer from 1 to "
            f"{MAX_LEAD_DISCUSSION_TURNS}"
        )
    bindings = _ordered_bindings(
        snapshot.participant_ids, participant_bindings
    )
    context = build_lead_discussion_context(snapshot, visit_id=visit.visit_id)
    segment_index = len(visit.conversation_run_ids) + 1
    run_id = id_factory.discussion_segment_id(
        visit.visit_index, segment_index
    )
    conversation_run = simulate_chat(
        participants=bindings,
        speaker_selector=RoundRobinSelector() if selector is None else selector,
        topic=context,
        turn_count=turn_count,
        seed=seed,
        run_id=run_id,
        timestamp=timestamp,
        turn_reply_generator=_LeadDiscussionReplyGenerator(
            visit_index=visit.visit_index,
            segment_index=segment_index,
        ),
    )
    conversation_run = ConversationRun.model_validate(
        conversation_run.model_dump(mode="python")
    )
    visit_payload = visit.model_dump(mode="python")
    visit_payload["conversation_run_ids"] = (
        *visit.conversation_run_ids,
        conversation_run.run_id,
    )
    updated_visit = LeadVisit.model_validate(visit_payload)
    visits = tuple(
        updated_visit if item.visit_id == visit.visit_id else item
        for item in snapshot.visits
    )
    payload = snapshot.model_dump(mode="python")
    payload.update(
        visits=visits,
        conversation_runs=(*snapshot.conversation_runs, conversation_run),
    )
    updated_session = InvestigationSession.model_validate(payload)
    return LeadDiscussionResult(
        session=updated_session,
        conversation_run=conversation_run,
        context=context,
    )


def record_visit_analysis(
    session: InvestigationSession,
    *,
    visit_id: str,
    agent_id: str,
    facts: Sequence[str] = (),
    deductions: Sequence[str] = (),
    evidence: Sequence[EvidenceReference] = (),
    proposed_leads: Sequence[str] = (),
    id_factory: DeterministicInvestigationIdFactory,
) -> InvestigationSession:
    """Optionally append one caller-supplied visit analysis without gating."""
    snapshot = _validated_snapshot(session, id_factory)
    visit = _require_current_visit(snapshot, visit_id)
    if agent_id not in snapshot.participant_ids:
        raise ValueError("analysis agent_id must be a session participant")
    analysis = AgentAnalysis(
        analysis_id=id_factory.visit_analysis_id(agent_id, visit.visit_index),
        session_id=snapshot.session_id,
        origin_visit_id=visit.visit_id,
        lead_id=visit.lead_id,
        agent_id=agent_id,
        visible_clue_ids=(),
        facts=tuple(facts),
        deductions=tuple(deductions),
        evidence=tuple(evidence),
        proposed_leads=tuple(proposed_leads),
    )
    payload = snapshot.model_dump(mode="python")
    payload["analyses"] = (*snapshot.analyses, analysis)
    return InvestigationSession.model_validate(payload)


def record_hypothesis(
    session: InvestigationSession,
    *,
    origin_visit_id: str,
    statement: str,
    status: HypothesisStatus,
    evidence: Sequence[EvidenceReference] = (),
    previous_hypothesis_id: str | None = None,
    id_factory: DeterministicInvestigationIdFactory,
) -> InvestigationSession:
    """Optionally append a visit-originated hypothesis."""
    snapshot = _validated_snapshot(session, id_factory)
    _require_current_visit(snapshot, origin_visit_id)
    hypothesis = Hypothesis(
        hypothesis_id=id_factory.hypothesis_id(len(snapshot.hypotheses) + 1),
        session_id=snapshot.session_id,
        origin_visit_id=origin_visit_id,
        statement=statement,
        status=status,
        evidence=tuple(evidence),
        previous_hypothesis_id=previous_hypothesis_id,
    )
    payload = snapshot.model_dump(mode="python")
    payload["hypotheses"] = (*snapshot.hypotheses, hypothesis)
    return InvestigationSession.model_validate(payload)


def record_group_decision(
    session: InvestigationSession,
    *,
    origin_visit_id: str,
    decision_type: GroupDecisionType,
    summary: str,
    analysis_ids: Sequence[str] = (),
    hypothesis_ids: Sequence[str] = (),
    evidence: Sequence[EvidenceReference] = (),
    id_factory: DeterministicInvestigationIdFactory,
) -> InvestigationSession:
    """Optionally append a non-gating visit-originated group decision."""
    snapshot = _validated_snapshot(session, id_factory)
    visit = _require_current_visit(snapshot, origin_visit_id)
    decision = GroupDecision(
        decision_id=id_factory.decision_id(len(snapshot.decisions) + 1),
        session_id=snapshot.session_id,
        origin_visit_id=visit.visit_id,
        lead_id=visit.lead_id,
        decision_type=decision_type,
        summary=summary,
        analysis_ids=tuple(analysis_ids),
        hypothesis_ids=tuple(hypothesis_ids),
        evidence=tuple(evidence),
    )
    payload = snapshot.model_dump(mode="python")
    payload["decisions"] = (*snapshot.decisions, decision)
    return InvestigationSession.model_validate(payload)


def _render_lead_finalization_values(
    session: InvestigationSession,
) -> dict[str, str]:
    run_by_id = {item.run_id: item for item in session.conversation_runs}
    return {
        "session_id": session.session_id,
        "case_introduction": session.case_introduction,
        "leads": "\n".join(
            f"[{item.lead_id}] {item.label} ({item.kind})"
            for item in session.leads
        ) or "None.",
        "visits": "\n".join(
            f"{item.visit_index}. [{item.visit_id}] lead={item.lead_id}"
            for item in session.visits
        ) or "None.",
        "revealed_information": "\n".join(
            f"{item.reveal_index + 1}. [{item.information_id}] {item.text}"
            for item in session.revealed_information
        ) or "None.",
        "discussion_history": "\n".join(
            f"[{message.run_id} turn {message.turn_index}] "
            f"{message.speaker_name}: {message.text}"
            for visit in session.visits
            for run_id in visit.conversation_run_ids
            for message in run_by_id[run_id].messages
        ) or "None.",
        "hypotheses": render_hypotheses(session.hypotheses),
        "decisions": render_decisions(session.decisions),
    }


def finalize_lead_investigation(
    session: InvestigationSession,
    *,
    final_theory_provider: LLMProvider,
    id_factory: DeterministicInvestigationIdFactory,
) -> LeadFinalizationResult:
    """Explicitly finalize valid Lead/Visit history without reasoning gates."""
    snapshot = _validated_snapshot(session, id_factory)
    if snapshot.conclusion_mode is not ConclusionMode.GENERATED_FINAL_THEORY:
        raise GameplayConflictError("this case does not use generated final theory")
    if not snapshot.visits:
        raise ValueError("finalization requires at least one lead visit")
    if not snapshot.revealed_information:
        raise ValueError("finalization requires revealed information")
    if snapshot.final_theory is not None:
        raise ValueError("investigation already contains a final theory")
    if not callable(getattr(final_theory_provider, "generate", None)):
        raise ValueError(
            "final_theory_provider must implement the LLMProvider boundary"
        )
    prompt = render_investigation_prompt(
        load_investigation_prompt(InvestigationPromptName.LEAD_FINAL_THEORY),
        _render_lead_finalization_values(snapshot),
    )
    generation = final_theory_provider.generate(
        prompt, task_name=investigation_lead_final_theory_task_name()
    )
    structured = parse_structured_generation(
        generation, GeneratedFinalTheoryPayload
    )
    generated = structured.value
    information_ids = {
        item.information_id for item in snapshot.revealed_information
    }
    if not generated.evidence:
        raise ValueError("final theory requires at least one evidence reference")
    if any(
        item.information_id not in information_ids
        for item in generated.evidence
    ):
        raise ValueError(
            "final theory evidence must reference revealed information"
        )
    hypothesis_ids = {item.hypothesis_id for item in snapshot.hypotheses}
    if any(item not in hypothesis_ids for item in generated.hypothesis_ids):
        raise ValueError("final theory references an unknown hypothesis")
    final_theory = FinalTheory(
        final_theory_id=id_factory.final_theory_id(),
        summary=generated.summary,
        hypothesis_ids=generated.hypothesis_ids,
        evidence=generated.evidence,
    )
    payload = snapshot.model_dump(mode="python")
    payload.update(status=InvestigationStatus.COMPLETED, final_theory=final_theory)
    completed = InvestigationSession.model_validate(payload)
    return LeadFinalizationResult(
        session=completed,
        final_theory=final_theory,
        generation=structured,
    )
