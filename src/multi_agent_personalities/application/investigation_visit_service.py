"""Stateless application operations for Lead/Visit investigations."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from multi_agent_personalities.application.investigation_ids import (
    DeterministicInvestigationIdFactory,
)
from multi_agent_personalities.models import (
    ConversationRun,
    InvestigationLead,
    InvestigationSession,
    InvestigationStatus,
    LeadVisit,
    Message,
    RevealedInformation,
)
from multi_agent_personalities.simulation import (
    RoundRobinSelector,
    SpeakerSelector,
    simulate_chat,
)
from multi_agent_personalities.simulation.participant import (
    ConversationParticipant,
)


MAX_LEAD_DISCUSSION_TURNS = 100


@dataclass(frozen=True)
class LeadDiscussionResult:
    """One atomic session update and its bounded discussion segment."""

    session: InvestigationSession
    conversation_run: ConversationRun
    context: str


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
            label=label,
            kind=kind,
        )
        updated_leads = (*snapshot.leads, resolved_lead)
    else:
        if label is not None or kind is not None:
            raise ValueError("label and kind must be omitted when revisiting a lead")
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
    )
    payload = snapshot.model_dump(mode="python")
    payload.update(leads=updated_leads, visits=(*snapshot.visits, new_visit))
    return InvestigationSession.model_validate(payload)


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
    visit = _visit_by_id(snapshot, visit_id)
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
    visit = _visit_by_id(snapshot, visit_id)
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
