"""Server-side presentation models for the Lead/Visit investigation UI."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from multi_agent_personalities.case_catalog import CaseCatalog, CaseResourceType
from multi_agent_personalities.pipeline import CharacterConfig
from multi_agent_personalities.application.investigation_visit_service import (
    project_lead_conversation,
    pending_case_interaction,
)
from multi_agent_personalities.case_content_catalog import CaseContentCatalog
from multi_agent_personalities.models import InvestigationStatus, Message
from multi_agent_personalities.web.investigation_store import InvestigationSessionRecord

def _initials(display_name: str) -> str:
    words = display_name.split()
    if not words:
        return "?"
    return "".join(word[0].upper() for word in (words[0], words[-1]))


@dataclass(frozen=True)
class InvestigationParticipantPresentation:
    slug: str
    display_name: str
    description: str
    lobby_description: str
    initials: str
    presentation_class: str
    selected: bool
    supported: bool


@dataclass(frozen=True)
class InvestigationResourcePresentation:
    resource_id: str
    type: str
    title: str
    description: str
    date: str | None
    asset_available: bool
    asset_url: str | None


@dataclass(frozen=True)
class InvestigationInteractionPresentation:
    interaction_id: str
    prompt: str
    options: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class InvestigationResourceGroupPresentation:
    key: str
    label: str
    resources: tuple[InvestigationResourcePresentation, ...]
    map_selector: bool


@dataclass(frozen=True)
class InvestigationSessionPresentation:
    session_id: str
    case_title: str
    case_short_description: str
    introduction: str
    status: str
    participants: tuple[InvestigationParticipantPresentation, ...]
    lead_count: int
    visit_count: int
    is_case_opening: bool
    resource_groups: tuple[InvestigationResourceGroupPresentation, ...]
    leads: tuple["InvestigationLeadPresentation", ...]
    selected_lead: "InvestigationLeadDetailPresentation | None"
    completed: bool
    can_finalize: bool
    final_theory: "InvestigationFinalTheoryPresentation | None"
    modes: tuple[str, ...]
    lead_budget_remaining: int | None


@dataclass(frozen=True)
class InvestigationLeadPresentation:
    lead_id: str
    label: str
    kind: str
    reference: str | None
    visit_count: int
    selected: bool
    current: bool
    revisited: bool


@dataclass(frozen=True)
class InvestigationMessagePresentation:
    display_name: str
    initials: str
    text: str
    presentation_class: str


@dataclass(frozen=True)
class InvestigationInformationPresentation:
    text: str


@dataclass(frozen=True)
class InvestigationVisitPresentation:
    visit_index: int
    marker: str
    current: bool
    information: tuple[InvestigationInformationPresentation, ...]
    messages: tuple[InvestigationMessagePresentation, ...]


@dataclass(frozen=True)
class InvestigationLeadDetailPresentation:
    lead_id: str
    label: str
    kind: str
    reference: str | None
    current: bool
    writable_visit_id: str | None
    visits: tuple[InvestigationVisitPresentation, ...]
    message_count: int
    interaction: InvestigationInteractionPresentation | None


@dataclass(frozen=True)
class InvestigationFinalEvidencePresentation:
    relation: str
    text: str


@dataclass(frozen=True)
class InvestigationFinalTheoryPresentation:
    summary: str
    evidence: tuple[InvestigationFinalEvidencePresentation, ...]
    hypotheses: tuple[str, ...]


def catalogue_participants(
    catalogue: Mapping[str, CharacterConfig],
    *,
    supported_character_ids: Sequence[str],
    selected_slugs: Sequence[str],
) -> tuple[InvestigationParticipantPresentation, ...]:
    """Present every catalogue entry without making fixture support a rule."""
    supported = set(supported_character_ids)
    selected = set(selected_slugs)
    return tuple(
        InvestigationParticipantPresentation(
            slug=config.slug,
            display_name=config.display_name,
            description=config.description,
            lobby_description={
                "sherlock": "Analytical, observational, and deductive.",
                "poirot": "Methodical, psychological, and orderly.",
            }.get(config.slug, config.description),
            initials=_initials(config.display_name),
            presentation_class=f"participant-tone-{index % 4 + 1}",
            selected=config.slug in selected,
            supported=config.character_id in supported,
        )
        for index, config in enumerate(catalogue.values())
    )


def _message_presentation(
    message: Message,
    participants_by_id: Mapping[str, InvestigationParticipantPresentation],
) -> InvestigationMessagePresentation:
    participant = participants_by_id[message.speaker_character_id]
    participant_index = tuple(participants_by_id).index(message.speaker_character_id)
    return InvestigationMessagePresentation(
        display_name=participant.display_name,
        initials=participant.initials,
        text=message.text,
        presentation_class=f"participant-tone-{participant_index % 4 + 1}",
    )


def present_session(
    record: InvestigationSessionRecord,
    *,
    case_catalog: CaseCatalog,
    resource_base_directory: Path,
    selected_lead_id: str | None = None,
    case_content_catalog: CaseContentCatalog | None = None,
) -> InvestigationSessionPresentation:
    """Project an immutable Lead/Visit snapshot for the web shell."""
    participants = tuple(
        InvestigationParticipantPresentation(
            slug=config.slug,
            display_name=config.display_name,
            description=config.description,
            lobby_description=config.description,
            initials=_initials(config.display_name),
            presentation_class=f"participant-tone-{index % 4 + 1}",
            selected=True,
            supported=True,
        )
        for index, config in enumerate(record.runtime.character_configs)
    )
    session = record.session
    case_definition = case_catalog.get(session.case_id)
    completed = session.status is InvestigationStatus.COMPLETED or bool(session.case_state and session.case_state.outcome)
    lead_by_id = {lead.lead_id: lead for lead in session.leads}
    current_visit = session.visits[-1] if session.visits else None
    resolved_lead_id = (
        selected_lead_id
        if selected_lead_id is not None
        else (current_visit.lead_id if current_visit is not None else None)
    )
    if resolved_lead_id is not None and resolved_lead_id not in lead_by_id:
        raise ValueError(f"unknown lead_id: {resolved_lead_id!r}")
    visit_counts = {
        lead_id: sum(visit.lead_id == lead_id for visit in session.visits)
        for lead_id in lead_by_id
    }
    leads = tuple(
        InvestigationLeadPresentation(
            lead_id=lead.lead_id,
            label=lead.label,
            kind=lead.kind,
            reference=lead.reference,
            visit_count=visit_counts[lead.lead_id],
            selected=lead.lead_id == resolved_lead_id,
            current=(
                current_visit is not None
                and lead.lead_id == current_visit.lead_id
            ),
            revisited=visit_counts[lead.lead_id] > 1,
        )
        for lead in session.leads
    )
    selected_detail = None
    if resolved_lead_id is not None:
        selected_lead = lead_by_id[resolved_lead_id]
        projected_messages = project_lead_conversation(session, resolved_lead_id)
        visit_id_by_run_id = {
            run_id: visit.visit_id
            for visit in session.visits
            if visit.lead_id == resolved_lead_id
            for run_id in visit.conversation_run_ids
        }
        projected_messages_by_visit = {
            visit.visit_id: []
            for visit in session.visits
            if visit.lead_id == resolved_lead_id
        }
        for message in projected_messages:
            projected_messages_by_visit[
                visit_id_by_run_id[message.run_id]
            ].append(message)
        information_by_id = {
            item.information_id: item for item in session.revealed_information
        }
        participants_by_id = {
            participant_id: participant
            for participant_id, participant in zip(
                session.participant_ids, participants, strict=True
            )
        }
        selected_visits = []
        for visit in session.visits:
            if visit.lead_id != resolved_lead_id:
                continue
            selected_visits.append(
                InvestigationVisitPresentation(
                    visit_index=visit.visit_index,
                    marker=(
                        "First visit"
                        if not selected_visits
                        else f"Revisited · Visit {visit.visit_index}"
                    ),
                    current=(
                        current_visit is not None
                        and visit.visit_id == current_visit.visit_id
                    ),
                    information=tuple(
                        InvestigationInformationPresentation(
                            information_by_id[item_id].text
                        )
                        for item_id in visit.revealed_information_ids
                    ),
                    messages=tuple(
                        _message_presentation(message, participants_by_id)
                        for message in projected_messages_by_visit[
                            visit.visit_id
                        ]
                    ),
                )
            )
        is_current = not completed and (
            current_visit is not None
            and current_visit.lead_id == resolved_lead_id
        )
        content = case_content_catalog.get(session.case_id) if case_content_catalog else None
        pending = pending_case_interaction(session, case_content=content, visit_id=current_visit.visit_id) if content is not None and is_current and current_visit is not None else None
        selected_detail = InvestigationLeadDetailPresentation(
            lead_id=selected_lead.lead_id,
            label=selected_lead.label,
            kind=selected_lead.kind,
            reference=selected_lead.reference,
            current=is_current,
            writable_visit_id=current_visit.visit_id if is_current else None,
            visits=tuple(selected_visits),
            message_count=len(projected_messages),
            interaction=(InvestigationInteractionPresentation(
                interaction_id=pending.interaction_id,
                prompt=pending.prompt_texts["en"],
                options=tuple((x.option_id, x.label_texts["en"]) for x in pending.options),
            ) if pending else None),
        )
    information_by_id = {
        item.information_id: item for item in session.revealed_information
    }
    hypothesis_by_id = {
        item.hypothesis_id: item for item in session.hypotheses
    }
    final_theory = (
        InvestigationFinalTheoryPresentation(
            summary=session.final_theory.summary,
            evidence=tuple(
                InvestigationFinalEvidencePresentation(
                    relation=reference.relation.value.title(),
                    text=information_by_id[reference.information_id].text,
                )
                for reference in session.final_theory.evidence
                if reference.information_id is not None
            ),
            hypotheses=tuple(
                hypothesis_by_id[item].statement
                for item in session.final_theory.hypothesis_ids
            ),
        )
        if session.final_theory is not None
        else None
    )
    return InvestigationSessionPresentation(
        session_id=session.session_id,
        case_title=case_definition.title,
        case_short_description=case_definition.short_description,
        introduction=session.case_introduction,
        status=("Ended" if session.case_state and session.case_state.outcome else session.status.value.replace("_", " ").title()),
        participants=participants,
        lead_count=len(session.leads),
        visit_count=len(session.visits),
        is_case_opening=not session.visits,
        resource_groups=_resource_groups(
            case_catalog,
            case_id=session.case_id,
            resource_base_directory=resource_base_directory,
        ),
        leads=leads,
        selected_lead=selected_detail,
        completed=completed,
        can_finalize=(
            session.status is InvestigationStatus.ACTIVE
            and bool(session.visits)
            and bool(session.revealed_information)
            and session.final_theory is None
        ),
        final_theory=final_theory,
        modes=(case_content_catalog.get(session.case_id).state.modes if case_content_catalog and case_content_catalog.get(session.case_id) else ()),
        lead_budget_remaining=(session.case_state.lead_budget_remaining if session.case_state else None),
    )


def _resource_groups(
    case_catalog: CaseCatalog,
    *,
    case_id: str,
    resource_base_directory: Path,
) -> tuple[InvestigationResourceGroupPresentation, ...]:
    labels = {
        CaseResourceType.MAP: "Maps",
        CaseResourceType.NEWSPAPER: "Newspapers",
        CaseResourceType.DIRECTORY: "Directory",
        CaseResourceType.INFORMANTS: "Informants",
        CaseResourceType.DOCUMENT: "Documents",
        CaseResourceType.HANDOUT: "Handouts",
    }
    visible = tuple(
        resource
        for resource in case_catalog.resources_for_case(case_id)
        if resource.initially_available
    )
    ordered_types = tuple(dict.fromkeys(resource.type for resource in visible))
    groups = []
    for resource_type in ordered_types:
        resources = tuple(
            InvestigationResourcePresentation(
                resource_id=resource.resource_id,
                type=resource.type.value,
                title=resource.title,
                description=(
                    resource.description
                    or "No local description is configured."
                ),
                date=(resource.date.isoformat() if resource.date else None),
                asset_available=(
                    resource.asset_path is not None
                    and (
                        Path(resource_base_directory) / resource.asset_path
                    ).is_file()
                ),
                asset_url=(f"/case-assets/{resource.asset_path.as_posix()}" if resource.asset_path is not None else None),
            )
            for resource in visible
            if resource.type is resource_type
        )
        groups.append(
            InvestigationResourceGroupPresentation(
                key=f"resources-{resource_type.value}",
                label=labels[resource_type],
                resources=resources,
                map_selector=(
                    resource_type is CaseResourceType.MAP
                    and len(resources) > 1
                ),
            )
        )
    return tuple(groups)
