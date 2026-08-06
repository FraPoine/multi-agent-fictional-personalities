"""Stateless application operations for deterministic investigation work."""

from collections.abc import Sequence
from dataclasses import dataclass

from multi_agent_personalities.application.investigation_ids import (
    DeterministicInvestigationIdFactory,
)
from multi_agent_personalities.application.investigation_mock import (
    investigation_analysis_task_name,
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
    StructuredGenerationResult,
    parse_structured_generation,
)
from multi_agent_personalities.models import (
    AgentAnalysis,
    Clue,
    Hypothesis,
    InvestigationRound,
    InvestigationRoundStatus,
    InvestigationSession,
    InvestigationStatus,
)
from multi_agent_personalities.simulation.participant import (
    ConversationParticipant,
)


@dataclass(frozen=True)
class IndependentAnalysesResult:
    """One atomic analysis update and its ordered generation provenance."""

    session: InvestigationSession
    generations: tuple[
        StructuredGenerationResult[GeneratedAnalysisPayload], ...
    ]


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
    existing_hypothesis_ids = {item.hypothesis_id for item in snapshot.hypotheses}
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
            hypothesis_id = id_factory.hypothesis_id(next_hypothesis_index)
            if (
                hypothesis_id in existing_hypothesis_ids
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
