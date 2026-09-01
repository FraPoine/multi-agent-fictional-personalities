"""Stateless application operations for Lead/Visit investigations."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

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
    return InvestigationSession(
        session_id=id_factory.session_id,
        case_id=case_id,
        case_introduction=introduction,
        participant_ids=tuple(participant_ids),
        status=InvestigationStatus.ACTIVE,
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
