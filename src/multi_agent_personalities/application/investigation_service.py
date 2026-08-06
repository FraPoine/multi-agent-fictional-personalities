"""Stateless application operations for deterministic investigation work."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from multi_agent_personalities.application.investigation_discussion import (
    InvestigationDiscussionReplyGenerator,
)
from multi_agent_personalities.application.investigation_ids import (
    DeterministicInvestigationIdFactory,
)
from multi_agent_personalities.application.investigation_tasks import (
    investigation_analysis_task_name,
    investigation_decision_task_name,
)
from multi_agent_personalities.application.investigation_prompts import (
    InvestigationPromptName,
    load_investigation_prompt,
    render_analyses,
    render_decisions,
    render_discussion_messages,
    render_hypotheses,
    render_investigation_prompt,
    render_persona_context,
    render_visible_clues,
)
from multi_agent_personalities.application.investigation_structured_output import (
    GeneratedAnalysisPayload,
    GeneratedDecisionPayload,
    StructuredGenerationResult,
    parse_structured_generation,
)
from multi_agent_personalities.llm.base import LLMProvider
from multi_agent_personalities.models import (
    AgentAnalysis,
    Clue,
    ConversationRun,
    GroupDecision,
    Hypothesis,
    InvestigationRound,
    InvestigationRoundStatus,
    InvestigationSession,
    InvestigationStatus,
)
from multi_agent_personalities.simulation.participant import (
    ConversationParticipant,
)
from multi_agent_personalities.simulation import (
    RoundRobinSelector,
    SpeakerSelector,
    simulate_chat,
)


MAX_DISCUSSION_TURNS = 100


@dataclass(frozen=True)
class IndependentAnalysesResult:
    """One atomic analysis update and its ordered generation provenance."""

    session: InvestigationSession
    generations: tuple[
        StructuredGenerationResult[GeneratedAnalysisPayload], ...
    ]


@dataclass(frozen=True)
class GroupDiscussionResult:
    """One atomic round update and its completed discussion run."""

    session: InvestigationSession
    conversation_run: ConversationRun


@dataclass(frozen=True)
class GroupDecisionResult:
    """One atomic round completion and its generation provenance."""

    session: InvestigationSession
    decision: GroupDecision
    generation: StructuredGenerationResult[GeneratedDecisionPayload]


def _completed_history_context(
    session: InvestigationSession,
) -> str:
    """Render only records owned by rounds completed before the newest round."""
    previous_round_ids = {
        item.round_id for item in session.rounds[:-1]
    }
    analyses = tuple(
        item for item in session.analyses if item.round_id in previous_round_ids
    )
    hypotheses = tuple(
        item for item in session.hypotheses if item.round_id in previous_round_ids
    )
    decisions = tuple(
        item for item in session.decisions if item.round_id in previous_round_ids
    )
    discussion_lines = []
    for investigation_round in session.rounds[:-1]:
        if investigation_round.discussion_run is not None:
            discussion_lines.append(
                f"Round {investigation_round.round_index} discussion:\n"
                + render_discussion_messages(
                    investigation_round.discussion_run.messages
                )
            )
    sections = (
        "Previous analyses:\n" + render_analyses(analyses),
        "Previous hypotheses:\n" + render_hypotheses(hypotheses),
        "Previous decisions:\n" + render_decisions(decisions),
        "Previous discussions:\n"
        + ("\n".join(discussion_lines) if discussion_lines else "None."),
    )
    return "\n\n".join(sections)


def _validate_participant_bindings(
    participant_ids: tuple[str, ...],
    participant_bindings: Sequence[ConversationParticipant],
) -> dict[str, ConversationParticipant]:
    if isinstance(participant_bindings, (str, bytes)) or not isinstance(
        participant_bindings, Sequence
    ):
        raise ValueError("participant_bindings must be a sequence")
    if any(
        not isinstance(item, ConversationParticipant)
        for item in participant_bindings
    ):
        raise ValueError(
            "every participant binding must be a ConversationParticipant"
        )
    binding_ids = tuple(item.character_id for item in participant_bindings)
    if len(binding_ids) != len(set(binding_ids)):
        raise ValueError("participant bindings must not contain duplicates")
    if set(binding_ids) != set(participant_ids) or len(binding_ids) != len(
        participant_ids
    ):
        raise ValueError("participant bindings must match session participants")
    return {item.character_id: item for item in participant_bindings}


def create_session(
    *,
    id_factory: DeterministicInvestigationIdFactory,
    introduction: str,
    participant_ids: Sequence[str],
) -> InvestigationSession:
    """Create one validated active investigation with no revealed state."""
    if not isinstance(id_factory, DeterministicInvestigationIdFactory):
        raise ValueError(
            "id_factory must be a DeterministicInvestigationIdFactory"
        )
    session_id = id_factory.session_id
    id_factory.clue_id(0)
    id_factory.round_id(1)
    if not isinstance(introduction, str) or not introduction.strip():
        raise ValueError("introduction must not be empty")
    if isinstance(participant_ids, (str, bytes)) or not isinstance(
        participant_ids, Sequence
    ):
        raise ValueError("participant_ids must be a sequence of identifiers")

    return InvestigationSession(
        session_id=session_id,
        case_introduction=introduction,
        participant_ids=tuple(participant_ids),
        status=InvestigationStatus.ACTIVE,
    )


def reveal_clue(
    session: InvestigationSession,
    *,
    clue_text: str,
    id_factory: DeterministicInvestigationIdFactory,
) -> InvestigationSession:
    """Reveal exactly one caller-supplied clue and open its analysis round."""
    if not isinstance(session, InvestigationSession):
        raise ValueError("session must be a validated InvestigationSession")
    session = InvestigationSession.model_validate(
        session.model_dump(mode="python")
    )
    if not isinstance(id_factory, DeterministicInvestigationIdFactory):
        raise ValueError(
            "id_factory must be a DeterministicInvestigationIdFactory"
        )
    if id_factory.session_id != session.session_id:
        raise ValueError("id_factory session_id must match the investigation session")
    if session.status is not InvestigationStatus.ACTIVE:
        raise ValueError("clues may be revealed only in an active session")
    if len(session.clues) != len(session.rounds):
        raise ValueError("session clue and round history is inconsistent")
    for index, investigation_round in enumerate(session.rounds):
        expected_visible_ids = tuple(
            item.clue_id for item in session.clues[: index + 1]
        )
        if (
            investigation_round.revealed_clue_id
            != session.clues[index].clue_id
            or investigation_round.visible_clue_ids != expected_visible_ids
        ):
            raise ValueError("session clue and round history is inconsistent")
    if any(
        item.status is not InvestigationRoundStatus.COMPLETED
        for item in session.rounds
    ):
        raise ValueError("cannot reveal a clue while any existing round is incomplete")
    if not isinstance(clue_text, str) or not clue_text.strip():
        raise ValueError("clue_text must not be empty")

    reveal_order = len(session.clues)
    resolved_clue_id = id_factory.clue_id(reveal_order)
    if any(item.clue_id == resolved_clue_id for item in session.clues):
        raise ValueError(f"duplicate clue_id: {resolved_clue_id!r}")

    round_index = len(session.rounds) + 1
    resolved_round_id = id_factory.round_id(round_index)
    if any(item.round_id == resolved_round_id for item in session.rounds):
        raise ValueError(f"duplicate round_id: {resolved_round_id!r}")
    new_clue = Clue(
        clue_id=resolved_clue_id,
        text=clue_text,
        reveal_order=reveal_order,
    )
    updated_clues = (*session.clues, new_clue)
    new_round = InvestigationRound(
        session_id=session.session_id,
        round_id=resolved_round_id,
        round_index=round_index,
        revealed_clue_id=resolved_clue_id,
        visible_clue_ids=tuple(item.clue_id for item in updated_clues),
        status=InvestigationRoundStatus.AWAITING_ANALYSES,
    )

    payload = session.model_dump(mode="python")
    payload.update(
        status=InvestigationStatus.ACTIVE,
        clues=updated_clues,
        rounds=(*session.rounds, new_round),
    )
    return InvestigationSession.model_validate(payload)


def run_independent_analyses(
    session: InvestigationSession,
    *,
    participant_bindings: Sequence[ConversationParticipant],
    id_factory: DeterministicInvestigationIdFactory,
) -> IndependentAnalysesResult:
    """Generate one independent analysis per participant as one atomic update."""
    if not isinstance(session, InvestigationSession):
        raise ValueError("session must be a validated InvestigationSession")
    snapshot = InvestigationSession.model_validate(
        session.model_dump(mode="python")
    )
    if snapshot.status is not InvestigationStatus.ACTIVE:
        raise ValueError("analyses may run only in an active session")
    if not snapshot.rounds:
        raise ValueError("analyses require a current investigation round")

    current_round = snapshot.rounds[-1]
    if current_round.status is not InvestigationRoundStatus.AWAITING_ANALYSES:
        raise ValueError("current round must be awaiting analyses")
    if current_round.analysis_ids or any(
        item.round_id == current_round.round_id for item in snapshot.analyses
    ):
        raise ValueError("current round already contains analyses")
    if current_round.discussion_run is not None:
        raise ValueError("current round must not contain a discussion")
    if current_round.decision_id is not None:
        raise ValueError("current round must not contain a decision")
    if any(
        item.status is not InvestigationRoundStatus.COMPLETED
        for item in snapshot.rounds[:-1]
    ):
        raise ValueError("all previous rounds must be completed")
    if not isinstance(id_factory, DeterministicInvestigationIdFactory):
        raise ValueError(
            "id_factory must be a DeterministicInvestigationIdFactory"
        )
    if id_factory.session_id != snapshot.session_id:
        raise ValueError("id_factory session_id must match the investigation session")

    binding_by_id = _validate_participant_bindings(
        snapshot.participant_ids,
        participant_bindings,
    )
    template = load_investigation_prompt(InvestigationPromptName.ANALYSIS)
    visible_clues = render_visible_clues(
        snapshot,
        current_round.visible_clue_ids,
    )
    completed_history = _completed_history_context(snapshot)

    prompts: list[tuple[ConversationParticipant, str, str, str]] = []
    existing_analysis_ids = {item.analysis_id for item in snapshot.analyses}
    planned_analysis_ids: set[str] = set()
    for participant_id in snapshot.participant_ids:
        binding = binding_by_id[participant_id]
        analysis_id = id_factory.analysis_id(
            participant_id,
            current_round.round_index,
        )
        if (
            analysis_id in existing_analysis_ids
            or analysis_id in planned_analysis_ids
        ):
            raise ValueError(f"duplicate analysis_id: {analysis_id!r}")
        planned_analysis_ids.add(analysis_id)
        rendered_prompt = render_investigation_prompt(
            template,
            {
                "session_id": snapshot.session_id,
                "round_id": current_round.round_id,
                "case_introduction": snapshot.case_introduction,
                "participant_id": participant_id,
                "persona_profile": render_persona_context(binding.persona),
                "visible_clues": visible_clues,
                "completed_history": completed_history,
            },
        )
        prompts.append(
            (
                binding,
                analysis_id,
                investigation_analysis_task_name(
                    participant_id,
                    current_round.round_index,
                ),
                rendered_prompt,
            )
        )

    structured_generations: list[
        StructuredGenerationResult[GeneratedAnalysisPayload]
    ] = []
    generated_analyses: list[AgentAnalysis] = []
    generated_hypotheses: list[Hypothesis] = []
    snapshot_hypothesis_ids = {
        item.hypothesis_id for item in snapshot.hypotheses
    }
    next_hypothesis_index = len(snapshot.hypotheses) + 1
    for binding, analysis_id, task_name, rendered_prompt in prompts:
        generation = binding.provider.generate(
            rendered_prompt,
            task_name=task_name,
        )
        if generation.metadata.provider != binding.provider_name:
            raise ValueError(
                "generation provider must match participant binding declaration"
            )
        if (
            binding.model_name is not None
            and generation.metadata.model is not None
            and generation.metadata.model != binding.model_name
        ):
            raise ValueError(
                "generation model must match participant binding declaration"
            )
        structured = parse_structured_generation(
            generation,
            GeneratedAnalysisPayload,
        )
        payload = structured.value
        generated_analyses.append(
            AgentAnalysis(
                analysis_id=analysis_id,
                session_id=snapshot.session_id,
                round_id=current_round.round_id,
                agent_id=binding.character_id,
                visible_clue_ids=current_round.visible_clue_ids,
                facts=payload.facts,
                deductions=payload.deductions,
                evidence=payload.evidence,
                proposed_leads=payload.proposed_leads,
            )
        )
        for proposed in payload.hypotheses:
            if (
                proposed.previous_hypothesis_id is not None
                and proposed.previous_hypothesis_id not in snapshot_hypothesis_ids
            ):
                raise ValueError(
                    "previous_hypothesis_id must reference a hypothesis in the pre-analysis snapshot"
                )
            hypothesis_id = id_factory.hypothesis_id(next_hypothesis_index)
            if (
                hypothesis_id in snapshot_hypothesis_ids
                or any(
                    item.hypothesis_id == hypothesis_id
                    for item in generated_hypotheses
                )
            ):
                raise ValueError(f"duplicate hypothesis_id: {hypothesis_id!r}")
            generated_hypotheses.append(
                Hypothesis(
                    hypothesis_id=hypothesis_id,
                    session_id=snapshot.session_id,
                    round_id=current_round.round_id,
                    statement=proposed.statement,
                    status=proposed.status,
                    evidence=proposed.evidence,
                    previous_hypothesis_id=proposed.previous_hypothesis_id,
                )
            )
            next_hypothesis_index += 1
        structured_generations.append(structured)

    round_payload = current_round.model_dump(mode="python")
    round_payload.update(
        analysis_ids=tuple(item.analysis_id for item in generated_analyses),
        status=InvestigationRoundStatus.AWAITING_DISCUSSION,
    )
    updated_round = InvestigationRound.model_validate(round_payload)
    session_payload = snapshot.model_dump(mode="python")
    session_payload.update(
        rounds=(*snapshot.rounds[:-1], updated_round),
        analyses=(*snapshot.analyses, *generated_analyses),
        hypotheses=(*snapshot.hypotheses, *generated_hypotheses),
    )
    updated_session = InvestigationSession.model_validate(session_payload)
    return IndependentAnalysesResult(
        session=updated_session,
        generations=tuple(structured_generations),
    )


def run_group_discussion(
    session: InvestigationSession,
    *,
    participant_bindings: Sequence[ConversationParticipant],
    id_factory: DeterministicInvestigationIdFactory,
    turn_count: int,
    selector: SpeakerSelector | None = None,
    seed: int = 42,
    timestamp: datetime | None = None,
) -> GroupDiscussionResult:
    """Run and atomically attach one complete current-round discussion."""
    if not isinstance(session, InvestigationSession):
        raise ValueError("session must be a validated InvestigationSession")
    snapshot = InvestigationSession.model_validate(
        session.model_dump(mode="python")
    )
    if snapshot.status is not InvestigationStatus.ACTIVE:
        raise ValueError("discussion may run only in an active session")
    if not snapshot.rounds:
        raise ValueError("discussion requires a current investigation round")
    if (
        isinstance(turn_count, bool)
        or not isinstance(turn_count, int)
        or not 1 <= turn_count <= MAX_DISCUSSION_TURNS
    ):
        raise ValueError(
            f"turn_count must be a strict integer from 1 to {MAX_DISCUSSION_TURNS}"
        )

    current_round = snapshot.rounds[-1]
    if current_round.status is not InvestigationRoundStatus.AWAITING_DISCUSSION:
        raise ValueError("current round must be awaiting discussion")
    if current_round.discussion_run is not None:
        raise ValueError("current round already contains a discussion")
    if current_round.decision_id is not None:
        raise ValueError("current round must not contain a decision")
    if any(
        item.status is not InvestigationRoundStatus.COMPLETED
        for item in snapshot.rounds[:-1]
    ):
        raise ValueError("all previous rounds must be completed")

    current_analyses = tuple(
        item
        for item in snapshot.analyses
        if item.round_id == current_round.round_id
    )
    if tuple(item.agent_id for item in current_analyses) != snapshot.participant_ids:
        raise ValueError(
            "current-round analyses must match session participant order exactly"
        )
    if current_round.analysis_ids != tuple(
        item.analysis_id for item in current_analyses
    ):
        raise ValueError(
            "current-round analysis_ids must match current analyses exactly"
        )
    if any(
        item.session_id != snapshot.session_id
        or item.round_id != current_round.round_id
        or item.visible_clue_ids != current_round.visible_clue_ids
        for item in current_analyses
    ):
        raise ValueError("current-round analysis ownership or visibility is invalid")

    if not isinstance(id_factory, DeterministicInvestigationIdFactory):
        raise ValueError(
            "id_factory must be a DeterministicInvestigationIdFactory"
        )
    if id_factory.session_id != snapshot.session_id:
        raise ValueError("id_factory session_id must match the investigation session")
    binding_by_id = _validate_participant_bindings(
        snapshot.participant_ids,
        participant_bindings,
    )
    ordered_bindings = tuple(
        binding_by_id[item] for item in snapshot.participant_ids
    )
    reply_generator = InvestigationDiscussionReplyGenerator(
        template=load_investigation_prompt(InvestigationPromptName.DISCUSSION),
        session_id=snapshot.session_id,
        round_id=current_round.round_id,
        round_index=current_round.round_index,
        case_introduction=snapshot.case_introduction,
        visible_clues=render_visible_clues(
            snapshot,
            current_round.visible_clue_ids,
        ),
        analyses=render_analyses(current_analyses),
        completed_history=_completed_history_context(snapshot),
    )
    conversation_run = simulate_chat(
        participants=ordered_bindings,
        speaker_selector=RoundRobinSelector() if selector is None else selector,
        topic=f"Investigation discussion for round {current_round.round_index}",
        turn_count=turn_count,
        seed=seed,
        run_id=id_factory.discussion_run_id(current_round.round_index),
        timestamp=timestamp,
        turn_reply_generator=reply_generator,
    )
    conversation_run = ConversationRun.model_validate(
        conversation_run.model_dump(mode="python")
    )

    round_payload = current_round.model_dump(mode="python")
    round_payload.update(
        discussion_run=conversation_run,
        status=InvestigationRoundStatus.AWAITING_DECISION,
    )
    updated_round = InvestigationRound.model_validate(round_payload)
    session_payload = snapshot.model_dump(mode="python")
    session_payload["rounds"] = (*snapshot.rounds[:-1], updated_round)
    updated_session = InvestigationSession.model_validate(session_payload)
    return GroupDiscussionResult(
        session=updated_session,
        conversation_run=conversation_run,
    )


def create_group_decision(
    session: InvestigationSession,
    *,
    decision_provider: LLMProvider,
    id_factory: DeterministicInvestigationIdFactory,
) -> GroupDecisionResult:
    """Generate and atomically record the current round's group decision."""
    if not isinstance(session, InvestigationSession):
        raise ValueError("session must be a validated InvestigationSession")
    snapshot = InvestigationSession.model_validate(
        session.model_dump(mode="python")
    )
    if snapshot.status is not InvestigationStatus.ACTIVE:
        raise ValueError("group decision may run only in an active session")
    if not snapshot.rounds:
        raise ValueError("group decision requires a current investigation round")
    if not callable(getattr(decision_provider, "generate", None)):
        raise ValueError("decision_provider must implement the LLMProvider boundary")
    if not isinstance(id_factory, DeterministicInvestigationIdFactory):
        raise ValueError(
            "id_factory must be a DeterministicInvestigationIdFactory"
        )
    if id_factory.session_id != snapshot.session_id:
        raise ValueError("id_factory session_id must match the investigation session")

    current_round = snapshot.rounds[-1]
    if current_round.status is not InvestigationRoundStatus.AWAITING_DECISION:
        raise ValueError("current round must be awaiting decision")
    if any(
        item.status is not InvestigationRoundStatus.COMPLETED
        for item in snapshot.rounds[:-1]
    ):
        raise ValueError("all previous rounds must be completed")
    if current_round.decision_id is not None or any(
        item.round_id == current_round.round_id for item in snapshot.decisions
    ):
        raise ValueError("current round already contains a decision")

    current_analyses = tuple(
        item
        for item in snapshot.analyses
        if item.round_id == current_round.round_id
    )
    if tuple(item.agent_id for item in current_analyses) != snapshot.participant_ids:
        raise ValueError(
            "current-round analyses must match session participant order exactly"
        )
    if current_round.analysis_ids != tuple(
        item.analysis_id for item in current_analyses
    ):
        raise ValueError(
            "current-round analysis_ids must match current analyses exactly"
        )
    if any(
        item.session_id != snapshot.session_id
        or item.visible_clue_ids != current_round.visible_clue_ids
        for item in current_analyses
    ):
        raise ValueError("current-round analysis ownership or visibility is invalid")

    discussion = current_round.discussion_run
    if discussion is None or discussion.status != "completed":
        raise ValueError("current round requires a completed discussion")
    if discussion.character_ids != snapshot.participant_ids:
        raise ValueError("discussion participants must match session participants")
    discussion = ConversationRun.model_validate(
        discussion.model_dump(mode="python")
    )

    available_hypotheses = tuple(
        item
        for item in snapshot.hypotheses
        if next(
            investigation_round.round_index
            for investigation_round in snapshot.rounds
            if investigation_round.round_id == item.round_id
        ) <= current_round.round_index
    )
    prompt = render_investigation_prompt(
        load_investigation_prompt(InvestigationPromptName.DECISION),
        {
            "session_id": snapshot.session_id,
            "round_id": current_round.round_id,
            "case_introduction": snapshot.case_introduction,
            "visible_clues": render_visible_clues(
                snapshot, current_round.visible_clue_ids
            ),
            "analyses": render_analyses(current_analyses),
            "hypotheses": render_hypotheses(available_hypotheses),
            "discussion_transcript": render_discussion_messages(
                discussion.messages
            ),
        },
    )
    generation = decision_provider.generate(
        prompt,
        task_name=investigation_decision_task_name(current_round.round_index),
    )
    structured = parse_structured_generation(
        generation,
        GeneratedDecisionPayload,
    )
    generated = structured.value

    current_analysis_ids = set(current_round.analysis_ids)
    if any(item not in current_analysis_ids for item in generated.analysis_ids):
        raise ValueError("decision analysis_ids must reference current-round analyses")
    snapshot_hypothesis_ids = {
        item.hypothesis_id for item in available_hypotheses
    }
    if any(item not in snapshot_hypothesis_ids for item in generated.hypothesis_ids):
        raise ValueError(
            "decision hypothesis_ids must reference pre-decision hypotheses"
        )
    visible_clue_ids = set(current_round.visible_clue_ids)
    if any(item.clue_id not in visible_clue_ids for item in generated.evidence):
        raise ValueError("decision evidence must reference visible clues")

    generated_hypotheses: list[Hypothesis] = []
    next_hypothesis_index = len(snapshot.hypotheses) + 1
    existing_hypothesis_ids = {item.hypothesis_id for item in snapshot.hypotheses}
    for proposed in generated.hypotheses:
        if (
            proposed.previous_hypothesis_id is not None
            and proposed.previous_hypothesis_id not in snapshot_hypothesis_ids
        ):
            raise ValueError(
                "previous_hypothesis_id must reference a hypothesis in the pre-decision snapshot"
            )
        if any(item.clue_id not in visible_clue_ids for item in proposed.evidence):
            raise ValueError("hypothesis evidence must reference visible clues")
        hypothesis_id = id_factory.hypothesis_id(next_hypothesis_index)
        if hypothesis_id in existing_hypothesis_ids or any(
            item.hypothesis_id == hypothesis_id for item in generated_hypotheses
        ):
            raise ValueError(f"duplicate hypothesis_id: {hypothesis_id!r}")
        generated_hypotheses.append(
            Hypothesis(
                hypothesis_id=hypothesis_id,
                session_id=snapshot.session_id,
                round_id=current_round.round_id,
                statement=proposed.statement,
                status=proposed.status,
                evidence=proposed.evidence,
                previous_hypothesis_id=proposed.previous_hypothesis_id,
            )
        )
        next_hypothesis_index += 1

    decision_id = id_factory.decision_id(current_round.round_index)
    if any(item.decision_id == decision_id for item in snapshot.decisions):
        raise ValueError(f"duplicate decision_id: {decision_id!r}")
    decision = GroupDecision(
        decision_id=decision_id,
        session_id=snapshot.session_id,
        round_id=current_round.round_id,
        decision_type=generated.decision_type,
        summary=generated.summary,
        analysis_ids=generated.analysis_ids,
        hypothesis_ids=generated.hypothesis_ids,
        evidence=generated.evidence,
    )
    round_payload = current_round.model_dump(mode="python")
    round_payload.update(
        decision_id=decision.decision_id,
        status=InvestigationRoundStatus.COMPLETED,
    )
    updated_round = InvestigationRound.model_validate(round_payload)
    session_payload = snapshot.model_dump(mode="python")
    session_payload.update(
        rounds=(*snapshot.rounds[:-1], updated_round),
        hypotheses=(*snapshot.hypotheses, *generated_hypotheses),
        decisions=(*snapshot.decisions, decision),
    )
    updated_session = InvestigationSession.model_validate(session_payload)
    return GroupDecisionResult(
        session=updated_session,
        decision=decision,
        generation=structured,
    )
