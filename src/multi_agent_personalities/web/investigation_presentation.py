"""Server-side presentation models for the Lead/Visit investigation UI."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from multi_agent_personalities.pipeline import CharacterConfig
from multi_agent_personalities.application.investigation_visit_service import (
    project_lead_conversation,
)
from multi_agent_personalities.models import Message
from multi_agent_personalities.web.investigation_store import InvestigationSessionRecord

DEMO_CASE_TITLE = "The Local Demonstration Case"


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
    initials: str
    selected: bool
    supported: bool


@dataclass(frozen=True)
class InvestigationResourcePresentation:
    label: str
    description: str
    available: bool


@dataclass(frozen=True)
class InvestigationSessionPresentation:
    session_id: str
    case_title: str
    introduction: str
    status: str
    participants: tuple[InvestigationParticipantPresentation, ...]
    lead_count: int
    visit_count: int
    is_case_opening: bool
    resources: tuple[InvestigationResourcePresentation, ...]
    leads: tuple["InvestigationLeadPresentation", ...]
    selected_lead: "InvestigationLeadDetailPresentation | None"


@dataclass(frozen=True)
class InvestigationLeadPresentation:
    lead_id: str
    label: str
    kind: str
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
    current: bool
    writable_visit_id: str | None
    visits: tuple[InvestigationVisitPresentation, ...]
    message_count: int


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
            initials=_initials(config.display_name),
            selected=config.slug in selected,
            supported=config.character_id in supported,
        )
        for config in catalogue.values()
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
    selected_lead_id: str | None = None,
) -> InvestigationSessionPresentation:
    """Project an immutable Lead/Visit snapshot for the web shell."""
    participants = tuple(
        InvestigationParticipantPresentation(
            slug=config.slug,
            display_name=config.display_name,
            description=config.description,
            initials=_initials(config.display_name),
            selected=True,
            supported=True,
        )
        for config in record.runtime.character_configs
    )
    session = record.session
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
        run_by_id = {run.run_id: run for run in session.conversation_runs}
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
            messages = tuple(
                message
                for run_id in visit.conversation_run_ids
                for message in run_by_id[run_id].messages
            )
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
                        for message in messages
                    ),
                )
            )
        is_current = (
            current_visit is not None
            and current_visit.lead_id == resolved_lead_id
        )
        selected_detail = InvestigationLeadDetailPresentation(
            lead_id=selected_lead.lead_id,
            label=selected_lead.label,
            kind=selected_lead.kind,
            current=is_current,
            writable_visit_id=current_visit.visit_id if is_current else None,
            visits=tuple(selected_visits),
            message_count=len(projected_messages),
        )
    return InvestigationSessionPresentation(
        session_id=session.session_id,
        case_title=DEMO_CASE_TITLE,
        introduction=session.case_introduction,
        status=session.status.value.replace("_", " ").title(),
        participants=participants,
        lead_count=len(session.leads),
        visit_count=len(session.visits),
        is_case_opening=not session.visits,
        resources=(
            InvestigationResourcePresentation("Case notes", "Review retained case information.", False),
            InvestigationResourcePresentation("Rules", "Read the local investigation guide.", True),
        ),
        leads=leads,
        selected_lead=selected_detail,
    )
