"""Original Sprint 7 round UI preserved pending its Lead/Visit UX redesign.

Registry, locking, creation, PRG, isolation, and error handling remain useful.
Phase-specific actions below are compatibility-only and are not the
authoritative investigation application contract.
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from multi_agent_personalities.application import (
    GroupDecisionResult,
    GroupDiscussionResult,
    IndependentAnalysesResult,
    InvestigationMockCapabilities,
    MAX_DISCUSSION_TURNS,
    continue_lead_discussion,
    create_group_decision,
    finalize_lead_investigation,
    investigation_mock_capabilities,
    reveal_clue,
    reveal_information,
    run_group_discussion,
    run_independent_analyses,
    visit_lead,
)
from multi_agent_personalities.models import (
    EvidenceReference,
    InvestigationRoundStatus,
    InvestigationStatus,
    validate_run_id,
)
from multi_agent_personalities.pipeline import CharacterConfig
from multi_agent_personalities.web.investigation_store import (
    InMemoryInvestigationRegistry,
    InvestigationRegistryInvariantError,
    InvestigationSessionMutation,
    InvestigationSessionCollisionError,
    InvestigationSessionNotFoundError,
    InvestigationSessionRecord,
)
from multi_agent_personalities.web.investigation_presentation import (
    DEMO_CASE_TITLE,
    catalogue_participants,
    present_session,
)


MAX_CASE_INTRODUCTION_LENGTH = 4000
MAX_CLUE_LENGTH = 4000
MAX_LEAD_LABEL_LENGTH = 160
MAX_LEAD_KIND_LENGTH = 80
MAX_INFORMATION_LENGTH = 4000
logger = logging.getLogger(__name__)


class InvestigationWorkflowConflictError(ValueError):
    """Raised when a browser action conflicts with the latest snapshot."""


class InvestigationResourceNotFoundError(ValueError):
    """Raised when a session-scoped Lead/Visit resource is unknown."""


@dataclass(frozen=True)
class InvestigationCharacterPresentation:
    """Catalogue identity paired with form-selection state."""

    config: CharacterConfig
    selected: bool


@dataclass(frozen=True)
class InvestigationEvidencePresentation:
    """One evidence relation resolved to user-facing clue content."""

    relation: str
    clue_number: int
    clue_text: str


@dataclass(frozen=True)
class InvestigationAnalysisPresentation:
    """One catalogue-identified analysis for server-side rendering."""

    display_name: str
    facts: tuple[str, ...]
    deductions: tuple[str, ...]
    evidence: tuple[InvestigationEvidencePresentation, ...]
    proposed_leads: tuple[str, ...]


@dataclass(frozen=True)
class InvestigationHypothesisPresentation:
    """One round-owned hypothesis without invented participant attribution."""

    statement: str
    status: str
    evidence: tuple[InvestigationEvidencePresentation, ...]
    previous_hypothesis_id: str | None


@dataclass(frozen=True)
class InvestigationDiscussionMessagePresentation:
    """One stored discussion message with catalogue display identity."""

    turn_number: int
    display_name: str
    text: str


@dataclass(frozen=True)
class InvestigationDecisionPresentation:
    """One completed decision with resolved user-facing references."""

    decision_type: str
    summary: str
    evidence: tuple[InvestigationEvidencePresentation, ...]
    analysis_references: tuple[str, ...]
    hypothesis_references: tuple[str, ...]


@dataclass(frozen=True)
class InvestigationFinalTheoryPresentation:
    """Completed final theory with resolved hypotheses and evidence."""

    summary: str
    hypothesis_references: tuple[str, ...]
    evidence: tuple[InvestigationEvidencePresentation, ...]


@dataclass(frozen=True)
class InvestigationReasoningGroupPresentation:
    """Ordered analysis and hypothesis history belonging to one round."""

    round_index: int
    analyses: tuple[InvestigationAnalysisPresentation, ...]
    hypotheses: tuple[InvestigationHypothesisPresentation, ...]
    discussion: tuple[InvestigationDiscussionMessagePresentation, ...]
    decision: InvestigationDecisionPresentation | None


def _supported_configs(
    catalogue: Mapping[str, CharacterConfig],
    capabilities: InvestigationMockCapabilities,
) -> tuple[CharacterConfig, ...]:
    by_id = {config.character_id: config for config in catalogue.values()}
    missing = tuple(
        participant_id
        for participant_id in capabilities.participant_ids
        if participant_id not in by_id
    )
    if missing:
        raise ValueError(
            "investigation mock participant is missing from the catalogue: "
            f"{missing[0]!r}"
        )
    return tuple(by_id[item] for item in capabilities.participant_ids)


def _validate_investigation_creation_form(
    *,
    characters: list[str] | None,
    introduction: str | None,
    known_slugs: Sequence[str],
    supported_slugs: Sequence[str],
) -> tuple[list[str], str, str, dict[str, str]]:
    """Validate user-controlled fields before runtime/session construction."""
    submitted = list(characters or [])
    known = set(known_slugs)
    supported = set(supported_slugs)
    selected = [slug for slug in submitted if slug in supported]
    raw_introduction = introduction or ""
    normalized_introduction = raw_introduction.strip()
    errors: dict[str, str] = {}

    if len(submitted) != len(set(submitted)):
        errors["characters"] = "Select each investigator only once."
    elif any(slug not in known for slug in submitted):
        errors["characters"] = "Select only characters in the current catalogue."
    elif any(slug not in supported for slug in submitted):
        errors["characters"] = (
            "Select only investigators supported by the current mock scenario."
        )
    elif len(submitted) < 2:
        errors["characters"] = "Select all supported investigators."
    elif set(submitted) != supported:
        errors["characters"] = (
            "Select the complete investigator set required by the mock scenario."
        )

    if not normalized_introduction:
        errors["introduction"] = "Enter a case introduction."
    elif len(raw_introduction) > MAX_CASE_INTRODUCTION_LENGTH:
        errors["introduction"] = (
            "Case introduction must be at most "
            f"{MAX_CASE_INTRODUCTION_LENGTH} characters."
        )

    return selected, normalized_introduction, raw_introduction, errors


def _index_context(
    *,
    registry: InMemoryInvestigationRegistry,
    catalogue: Mapping[str, CharacterConfig],
    supported_configs: Sequence[CharacterConfig],
    capabilities: InvestigationMockCapabilities,
    selected_slugs: Sequence[str] | None = None,
    introduction_value: str = "",
    field_errors: Mapping[str, str] | None = None,
    error_message: str | None = None,
) -> dict[str, object]:
    selected = (
        {item.slug for item in supported_configs}
        if selected_slugs is None
        else set(selected_slugs)
    )
    existing_records = tuple(
        registry.get(session_id) for session_id in registry.session_ids
    )
    return {
        "page_title": "Multi-Agent Fictional Personalities",
        "provider_name": "mock",
        "supported_characters": tuple(
            InvestigationCharacterPresentation(
                config=config,
                selected=config.slug in selected,
            )
            for config in supported_configs
        ),
        "investigator_options": catalogue_participants(
            catalogue,
            supported_character_ids=capabilities.participant_ids,
            selected_slugs=selected,
        ),
        "case_title": DEMO_CASE_TITLE,
        "capabilities": capabilities,
        "introduction_value": introduction_value,
        "field_errors": dict(field_errors or {}),
        "error_message": error_message,
        "existing_records": existing_records,
        "max_introduction_length": MAX_CASE_INTRODUCTION_LENGTH,
    }


def _can_reveal_clue(record: InvestigationSessionRecord) -> bool:
    session = record.session
    if session.status is not InvestigationStatus.ACTIVE:
        return False
    if len(session.rounds) >= record.runtime.capabilities.supported_rounds:
        return False
    return not session.rounds or all(
        item.status is InvestigationRoundStatus.COMPLETED
        for item in session.rounds
    )


def _can_run_analyses(record: InvestigationSessionRecord) -> bool:
    session = record.session
    return (
        session.status is InvestigationStatus.ACTIVE
        and bool(session.rounds)
        and session.rounds[-1].status
        is InvestigationRoundStatus.AWAITING_ANALYSES
        and session.rounds[-1].round_index
        <= record.runtime.capabilities.supported_rounds
    )


def _can_run_discussion(record: InvestigationSessionRecord) -> bool:
    session = record.session
    turn_count = record.runtime.capabilities.discussion_turns
    return (
        session.status is InvestigationStatus.ACTIVE
        and bool(session.rounds)
        and session.rounds[-1].status
        is InvestigationRoundStatus.AWAITING_DISCUSSION
        and session.rounds[-1].round_index
        <= record.runtime.capabilities.supported_rounds
        and not isinstance(turn_count, bool)
        and isinstance(turn_count, int)
        and 1 <= turn_count <= MAX_DISCUSSION_TURNS
    )


def _can_create_decision(record: InvestigationSessionRecord) -> bool:
    session = record.session
    return (
        session.status is InvestigationStatus.ACTIVE
        and bool(session.rounds)
        and session.rounds[-1].status
        is InvestigationRoundStatus.AWAITING_DECISION
        and session.rounds[-1].round_index
        <= record.runtime.capabilities.supported_rounds
    )


def _can_finalize_investigation(record: InvestigationSessionRecord) -> bool:
    session = record.session
    return (
        session.status is InvestigationStatus.ACTIVE
        and bool(session.rounds)
        and all(
            item.status is InvestigationRoundStatus.COMPLETED
            for item in session.rounds
        )
        and len(session.rounds)
        >= record.runtime.capabilities.supported_rounds
        and session.final_theory is None
    )


def _evidence_presentations(
    record: InvestigationSessionRecord,
    references: Sequence[EvidenceReference],
) -> tuple[InvestigationEvidencePresentation, ...]:
    clue_by_id = {
        clue.clue_id: (clue.reveal_order + 1, clue.text)
        for clue in record.session.clues
    }
    return tuple(
        InvestigationEvidencePresentation(
            relation=reference.relation.value.title(),
            clue_number=clue_by_id[reference.clue_id][0],
            clue_text=clue_by_id[reference.clue_id][1],
        )
        for reference in references
    )


def _final_theory_presentation(
    record: InvestigationSessionRecord,
) -> InvestigationFinalTheoryPresentation | None:
    final_theory = record.session.final_theory
    if final_theory is None:
        return None
    hypothesis_by_id = {
        hypothesis.hypothesis_id: hypothesis
        for hypothesis in record.session.hypotheses
    }
    return InvestigationFinalTheoryPresentation(
        summary=final_theory.summary,
        hypothesis_references=tuple(
            hypothesis_by_id[hypothesis_id].statement
            for hypothesis_id in final_theory.hypothesis_ids
        ),
        evidence=_evidence_presentations(record, final_theory.evidence),
    )


def _reasoning_groups(
    record: InvestigationSessionRecord,
) -> tuple[InvestigationReasoningGroupPresentation, ...]:
    session = record.session
    config_by_id = {
        config.character_id: config
        for config in record.runtime.character_configs
    }
    analysis_by_id = {
        analysis.analysis_id: analysis for analysis in session.analyses
    }
    analysis_display_by_id = {
        analysis_id: config_by_id[analysis.agent_id].display_name
        for analysis_id, analysis in analysis_by_id.items()
    }
    hypothesis_by_id = {
        hypothesis.hypothesis_id: hypothesis
        for hypothesis in session.hypotheses
    }
    decision_by_round_id = {
        decision.round_id: decision for decision in session.decisions
    }

    groups = []
    for investigation_round in session.rounds:
        analysis_by_participant = {
            analysis.agent_id: analysis
            for analysis in session.analyses
            if analysis.round_id == investigation_round.round_id
        }
        analyses = tuple(
            InvestigationAnalysisPresentation(
                display_name=config_by_id[participant_id].display_name,
                facts=analysis_by_participant[participant_id].facts,
                deductions=analysis_by_participant[participant_id].deductions,
                evidence=_evidence_presentations(
                    record,
                    analysis_by_participant[participant_id].evidence
                ),
                proposed_leads=(
                    analysis_by_participant[participant_id].proposed_leads
                ),
            )
            for participant_id in session.participant_ids
            if participant_id in analysis_by_participant
        )
        hypotheses = tuple(
            InvestigationHypothesisPresentation(
                statement=hypothesis.statement,
                status=hypothesis.status.value.title(),
                evidence=_evidence_presentations(record, hypothesis.evidence),
                previous_hypothesis_id=hypothesis.previous_hypothesis_id,
            )
            for hypothesis in session.hypotheses
            if hypothesis.round_id == investigation_round.round_id
        )
        discussion_run = investigation_round.discussion_run
        discussion = (
            tuple(
                InvestigationDiscussionMessagePresentation(
                    turn_number=message.turn_index + 1,
                    display_name=(
                        config_by_id[message.speaker_character_id].display_name
                    ),
                    text=message.text,
                )
                for message in discussion_run.messages
            )
            if discussion_run is not None
            else ()
        )
        stored_decision = decision_by_round_id.get(investigation_round.round_id)
        decision = (
            InvestigationDecisionPresentation(
                decision_type=stored_decision.decision_type.value.replace(
                    "_", " "
                ).title(),
                summary=stored_decision.summary,
                evidence=_evidence_presentations(record, stored_decision.evidence),
                analysis_references=tuple(
                    (
                        f"{analysis_display_by_id[analysis_id]} "
                        f"— Round {investigation_round.round_index} analysis"
                    )
                    for analysis_id in stored_decision.analysis_ids
                ),
                hypothesis_references=tuple(
                    hypothesis_by_id[hypothesis_id].statement
                    for hypothesis_id in stored_decision.hypothesis_ids
                ),
            )
            if stored_decision is not None
            else None
        )
        if analyses or hypotheses or discussion or decision is not None:
            groups.append(
                InvestigationReasoningGroupPresentation(
                    round_index=investigation_round.round_index,
                    analyses=analyses,
                    hypotheses=hypotheses,
                    discussion=discussion,
                    decision=decision,
                )
            )
    return tuple(groups)


def _workflow_state(record: InvestigationSessionRecord) -> str:
    if not record.session.rounds:
        return "Awaiting first clue"
    return record.session.rounds[-1].status.value.replace("_", " ").title()


def _workflow_message(record: InvestigationSessionRecord) -> str:
    session = record.session
    if session.status is InvestigationStatus.COMPLETED:
        return "This investigation is completed."
    if not session.rounds:
        return "Waiting for the Game Master to reveal the first clue."
    status = session.rounds[-1].status
    if status is InvestigationRoundStatus.COMPLETED:
        if len(session.rounds) >= record.runtime.capabilities.supported_rounds:
            return (
                "The deterministic mock scenario has no more clue rounds "
                "available."
            )
        return "Waiting for the Game Master to reveal the next clue."
    messages = {
        InvestigationRoundStatus.AWAITING_ANALYSES: (
            "Waiting for independent analyses."
        ),
        InvestigationRoundStatus.AWAITING_DISCUSSION: (
            "Waiting for group discussion."
        ),
        InvestigationRoundStatus.AWAITING_DECISION: (
            "Waiting for a group decision."
        ),
    }
    return messages[status]


def create_investigation_router(
    *,
    registry: InMemoryInvestigationRegistry,
    project_root: Path,
    catalogue: Mapping[str, CharacterConfig],
    templates: Jinja2Templates,
) -> APIRouter:
    """Create investigation routes over explicit app-owned dependencies."""
    router = APIRouter()
    capabilities = investigation_mock_capabilities()
    supported_configs = _supported_configs(catalogue, capabilities)
    known_slugs = tuple(catalogue)
    supported_slugs = tuple(config.slug for config in supported_configs)

    def render_error(
        request: Request,
        *,
        status_code: int,
        page_title: str,
        heading: str,
        message: str,
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="investigation_error.html",
            context={
                "page_title": page_title,
                "provider_name": "mock",
                "heading": heading,
                "message": message,
            },
            status_code=status_code,
        )

    def render_detail(
        request: Request,
        record: InvestigationSessionRecord,
        *,
        selected_lead_id: str | None = None,
        status_code: int = 200,
        clue_value: str = "",
        clue_error: str | None = None,
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="investigation_detail.html",
            context={
                "page_title": "Investigation session",
                "provider_name": "mock",
                "investigation": present_session(
                    record,
                    selected_lead_id=selected_lead_id,
                ),
            },
            status_code=status_code,
        )

    def render_index(
        request: Request,
        *,
        status_code: int = 200,
        **context: object,
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="investigations.html",
            context=_index_context(
                registry=registry,
                catalogue=catalogue,
                supported_configs=supported_configs,
                capabilities=capabilities,
                **context,
            ),
            status_code=status_code,
        )

    @router.get(
        "/investigations",
        response_class=HTMLResponse,
        name="investigations_index",
    )
    async def investigations_index(request: Request) -> HTMLResponse:
        """Render the side-effect-free local investigation creation page."""
        return render_index(request)

    @router.post(
        "/investigations",
        response_class=HTMLResponse,
        name="create_investigation",
    )
    async def create_investigation(
        request: Request,
        characters: Annotated[list[str] | None, Form()] = None,
        introduction: Annotated[str | None, Form()] = None,
    ) -> Response:
        """Validate and register one empty investigation, then redirect."""
        selected, normalized, raw, field_errors = (
            _validate_investigation_creation_form(
                characters=characters,
                introduction=introduction,
                known_slugs=known_slugs,
                supported_slugs=supported_slugs,
            )
        )
        if field_errors:
            return render_index(
                request,
                status_code=400,
                selected_slugs=selected,
                introduction_value=raw,
                field_errors=field_errors,
                error_message="Correct the highlighted fields and try again.",
            )

        try:
            record = registry.create(
                character_slugs=selected,
                introduction=normalized,
                project_root=project_root,
            )
        except InvestigationSessionCollisionError:
            logger.exception("Investigation session identifier collision")
            return render_index(
                request,
                status_code=409,
                selected_slugs=selected,
                introduction_value=raw,
                error_message=(
                    "The investigation identifier is already in use. Try again."
                ),
            )
        except (InvestigationRegistryInvariantError, OSError, ValueError):
            logger.exception("Local mock investigation creation failed")
            return render_index(
                request,
                status_code=500,
                selected_slugs=selected,
                introduction_value=raw,
                error_message=(
                    "The local mock investigation could not be created. "
                    "Check the project fixtures and try again."
                ),
            )

        return RedirectResponse(
            url=f"/investigations/{record.session_id}",
            status_code=303,
        )

    @router.get(
        "/investigations/{session_id}",
        response_class=HTMLResponse,
        name="investigation_detail",
    )
    async def investigation_detail(
        request: Request,
        session_id: str,
        lead: str | None = None,
    ) -> HTMLResponse:
        """Render the latest immutable snapshot on its canonical page."""
        try:
            validate_run_id(session_id)
            record = registry.get(session_id)
        except (ValueError, InvestigationSessionNotFoundError):
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message=(
                    "The requested investigation is not available in this "
                    "local process."
                ),
            )

        if lead is not None and not any(
            item.lead_id == lead for item in record.session.leads
        ):
            return render_error(
                request,
                status_code=404,
                page_title="Lead not found",
                heading="Lead not found",
                message="The selected lead does not belong to this investigation.",
            )
        return render_detail(request, record, selected_lead_id=lead)

    @router.post(
        "/investigations/{session_id}/leads",
        response_class=HTMLResponse,
        name="visit_new_investigation_lead",
    )
    async def visit_new_investigation_lead(
        request: Request,
        session_id: str,
        label: Annotated[str | None, Form()] = None,
        kind: Annotated[str | None, Form()] = None,
    ) -> Response:
        """Create and chronologically visit one new semantic lead."""
        raw_label = label or ""
        raw_kind = kind or ""
        normalized_label = raw_label.strip()
        normalized_kind = raw_kind.strip()
        if (
            not normalized_label
            or not normalized_kind
            or len(raw_label) > MAX_LEAD_LABEL_LENGTH
            or len(raw_kind) > MAX_LEAD_KIND_LENGTH
        ):
            return render_error(
                request,
                status_code=400,
                page_title="Invalid lead",
                heading="Lead could not be visited",
                message=(
                    "Enter a lead name and type within the displayed limits."
                ),
            )

        def mutate_new_lead(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[str]:
            if record.session.status is not InvestigationStatus.ACTIVE:
                raise InvestigationWorkflowConflictError(
                    "Completed investigations are read-only."
                )
            updated = visit_lead(
                record.session,
                id_factory=record.runtime.id_factory,
                label=normalized_label,
                kind=normalized_kind,
            )
            return InvestigationSessionMutation(
                session=updated,
                result=updated.leads[-1].lead_id,
            )

        try:
            _record, lead_id = registry.mutate(session_id, mutate_new_lead)
        except InvestigationSessionNotFoundError:
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message="The requested investigation is not available.",
            )
        except InvestigationWorkflowConflictError as error:
            return render_error(
                request,
                status_code=409,
                page_title="Investigation conflict",
                heading="Lead could not be visited",
                message=str(error),
            )
        except Exception:
            logger.exception("Creating a new investigation lead failed")
            return render_error(
                request,
                status_code=500,
                page_title="Investigation error",
                heading="Lead could not be visited",
                message="The previous investigation state was kept.",
            )
        return RedirectResponse(
            url=f"/investigations/{session_id}?lead={lead_id}", status_code=303
        )

    @router.post(
        "/investigations/{session_id}/leads/{lead_id}/visit",
        response_class=HTMLResponse,
        name="revisit_investigation_lead",
    )
    async def revisit_investigation_lead(
        request: Request, session_id: str, lead_id: str
    ) -> Response:
        """Explicitly create a new visit to an existing semantic lead."""
        def mutate_revisit(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[None]:
            if record.session.status is not InvestigationStatus.ACTIVE:
                raise InvestigationWorkflowConflictError(
                    "Completed investigations are read-only."
                )
            if not any(item.lead_id == lead_id for item in record.session.leads):
                raise InvestigationResourceNotFoundError(lead_id)
            if record.session.visits[-1].lead_id == lead_id:
                raise InvestigationWorkflowConflictError(
                    "the selected lead is already current"
                )
            updated = visit_lead(
                record.session,
                id_factory=record.runtime.id_factory,
                lead_id=lead_id,
            )
            return InvestigationSessionMutation(session=updated, result=None)

        response = _run_lead_mutation(
            request,
            session_id,
            mutate_revisit,
            failure_heading="Lead could not be revisited",
        )
        if response is not None:
            return response
        return RedirectResponse(
            url=f"/investigations/{session_id}?lead={lead_id}", status_code=303
        )

    def _current_visit_or_error(
        record: InvestigationSessionRecord, visit_id: str
    ) -> None:
        if record.session.status is not InvestigationStatus.ACTIVE:
            raise InvestigationWorkflowConflictError(
                "Completed investigations are read-only."
            )
        if not any(item.visit_id == visit_id for item in record.session.visits):
            raise InvestigationResourceNotFoundError(visit_id)
        if (
            not record.session.visits
            or record.session.visits[-1].visit_id != visit_id
        ):
            raise InvestigationWorkflowConflictError(
                "This historical visit is read-only. Revisit its lead explicitly."
            )

    def _run_lead_mutation(
        request: Request,
        session_id: str,
        operation: Callable[
            [InvestigationSessionRecord],
            InvestigationSessionMutation[object],
        ],
        *,
        failure_heading: str,
    ) -> Response | None:
        try:
            registry.mutate(session_id, operation)
        except (
            InvestigationSessionNotFoundError,
            InvestigationResourceNotFoundError,
        ):
            return render_error(
                request,
                status_code=404,
                page_title="Investigation resource not found",
                heading="Investigation resource not found",
                message="The requested session resource is not available.",
            )
        except InvestigationWorkflowConflictError as error:
            return render_error(
                request,
                status_code=409,
                page_title="Investigation conflict",
                heading=failure_heading,
                message=str(error),
            )
        except Exception:
            logger.exception("Lead/Visit investigation mutation failed")
            return render_error(
                request,
                status_code=500,
                page_title="Investigation error",
                heading=failure_heading,
                message="The previous investigation state was kept.",
            )
        return None

    @router.post(
        "/investigations/{session_id}/visits/{visit_id}/information",
        response_class=HTMLResponse,
        name="reveal_visit_information",
    )
    async def reveal_visit_information(
        request: Request,
        session_id: str,
        visit_id: str,
        information: Annotated[str | None, Form()] = None,
    ) -> Response:
        """Explicitly disclose information against the current visit."""
        raw = information or ""
        normalized = raw.strip()
        if not normalized or len(raw) > MAX_INFORMATION_LENGTH:
            return render_error(
                request,
                status_code=400,
                page_title="Invalid information",
                heading="Information could not be added",
                message=(
                    "Enter information up to "
                    f"{MAX_INFORMATION_LENGTH} characters."
                ),
            )

        def mutate_information(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[None]:
            _current_visit_or_error(record, visit_id)
            updated = reveal_information(
                record.session,
                visit_id=visit_id,
                information_texts=(normalized,),
                id_factory=record.runtime.id_factory,
            )
            return InvestigationSessionMutation(session=updated, result=None)

        response = _run_lead_mutation(
            request,
            session_id,
            mutate_information,
            failure_heading="Information could not be added",
        )
        if response is not None:
            return response
        record = registry.get(session_id)
        return RedirectResponse(
            url=f"/investigations/{session_id}?lead={record.session.visits[-1].lead_id}",
            status_code=303,
        )

    @router.post(
        "/investigations/{session_id}/visits/{visit_id}/discussion",
        response_class=HTMLResponse,
        name="continue_visit_discussion",
    )
    async def continue_visit_discussion(
        request: Request, session_id: str, visit_id: str
    ) -> Response:
        """Append one bounded discussion segment to the current visit."""
        def mutate_discussion(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[None]:
            _current_visit_or_error(record, visit_id)
            result = continue_lead_discussion(
                record.session,
                visit_id=visit_id,
                participant_bindings=record.runtime.participants,
                id_factory=record.runtime.id_factory,
                turn_count=record.runtime.capabilities.discussion_turns,
            )
            return InvestigationSessionMutation(session=result.session, result=None)

        response = _run_lead_mutation(
            request,
            session_id,
            mutate_discussion,
            failure_heading="Discussion could not continue",
        )
        if response is not None:
            return response
        record = registry.get(session_id)
        return RedirectResponse(
            url=f"/investigations/{session_id}?lead={record.session.visits[-1].lead_id}",
            status_code=303,
        )

    @router.post(
        "/investigations/{session_id}/clues",
        response_class=HTMLResponse,
        name="reveal_investigation_clue",
    )
    async def reveal_investigation_clue(
        request: Request,
        session_id: str,
        clue: Annotated[str | None, Form()] = None,
    ) -> Response:
        """Reveal one explicit clue against the latest locked snapshot."""
        try:
            validate_run_id(session_id)
        except ValueError:
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message=(
                    "The requested investigation is not available in this "
                    "local process."
                ),
            )

        raw_clue = clue or ""
        normalized_clue = raw_clue.strip()
        clue_error = None
        if not normalized_clue:
            clue_error = "Enter a clue."
        elif len(raw_clue) > MAX_CLUE_LENGTH:
            clue_error = f"Clue must be at most {MAX_CLUE_LENGTH} characters."
        if clue_error is not None:
            try:
                record = registry.get(session_id)
            except InvestigationSessionNotFoundError:
                return render_error(
                    request,
                    status_code=404,
                    page_title="Investigation not found",
                    heading="Investigation not found",
                    message=(
                        "The requested investigation is not available in this "
                        "local process."
                    ),
                )
            return render_detail(
                request,
                record,
                status_code=400,
                clue_value=raw_clue,
                clue_error=clue_error,
            )

        def mutate_clue(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[None]:
            if not _can_reveal_clue(record):
                raise InvestigationWorkflowConflictError(
                    "clue revelation is unavailable in the latest state"
                )
            updated = reveal_clue(
                record.session,
                clue_text=normalized_clue,
                id_factory=record.runtime.id_factory,
            )
            return InvestigationSessionMutation(session=updated, result=None)

        try:
            registry.mutate(session_id, mutate_clue)
        except InvestigationSessionNotFoundError:
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message=(
                    "The requested investigation is not available in this "
                    "local process."
                ),
            )
        except InvestigationRegistryInvariantError:
            logger.exception("Investigation registry invariant failure")
            return render_error(
                request,
                status_code=500,
                page_title="Investigation error",
                heading="Clue revelation failed",
                message=(
                    "The clue could not be revealed because of an unexpected "
                    "local error. The previous investigation state was kept."
                ),
            )
        except InvestigationWorkflowConflictError:
            return render_error(
                request,
                status_code=409,
                page_title="Investigation conflict",
                heading="Clue could not be revealed",
                message=(
                    "This investigation cannot accept a clue in its current "
                    "workflow state. Refresh the session page and try again."
                ),
            )
        except Exception:
            logger.exception("Local investigation clue revelation failed")
            return render_error(
                request,
                status_code=500,
                page_title="Investigation error",
                heading="Clue revelation failed",
                message=(
                    "The clue could not be revealed because of an unexpected "
                    "local error. The previous investigation state was kept."
                ),
            )

        return RedirectResponse(
            url=f"/investigations/{session_id}",
            status_code=303,
        )

    @router.post(
        "/investigations/{session_id}/analyses",
        response_class=HTMLResponse,
        name="run_investigation_analyses",
    )
    async def run_investigation_analyses(
        request: Request,
        session_id: str,
    ) -> Response:
        """Generate all current-round analyses as one locked mutation."""
        try:
            validate_run_id(session_id)
        except ValueError:
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message=(
                    "The requested investigation is not available in this "
                    "local process."
                ),
            )

        def mutate_analyses(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[IndependentAnalysesResult]:
            if not _can_run_analyses(record):
                raise InvestigationWorkflowConflictError(
                    "independent analyses are unavailable in the latest state"
                )
            result = run_independent_analyses(
                record.session,
                participant_bindings=record.runtime.participants,
                id_factory=record.runtime.id_factory,
            )
            return InvestigationSessionMutation(
                session=result.session,
                result=result,
            )

        try:
            _updated_record, _analysis_result = registry.mutate(
                session_id,
                mutate_analyses,
            )
        except InvestigationSessionNotFoundError:
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message=(
                    "The requested investigation is not available in this "
                    "local process."
                ),
            )
        except InvestigationWorkflowConflictError:
            return render_error(
                request,
                status_code=409,
                page_title="Investigation conflict",
                heading="Independent analyses could not run",
                message=(
                    "Independent analyses cannot run in the investigation's "
                    "current workflow state. Refresh the session page and "
                    "try again."
                ),
            )
        except Exception:
            logger.exception("Local independent analysis generation failed")
            return render_error(
                request,
                status_code=500,
                page_title="Investigation error",
                heading="Independent analyses failed",
                message=(
                    "Independent analyses could not be completed because of "
                    "an unexpected local generation error. The previous "
                    "investigation state was kept."
                ),
            )

        return RedirectResponse(
            url=f"/investigations/{session_id}",
            status_code=303,
        )

    @router.post(
        "/investigations/{session_id}/discussion",
        response_class=HTMLResponse,
        name="run_investigation_discussion",
    )
    async def run_investigation_discussion(
        request: Request,
        session_id: str,
    ) -> Response:
        """Generate one complete round-robin discussion under the lock."""
        try:
            validate_run_id(session_id)
        except ValueError:
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message=(
                    "The requested investigation is not available in this "
                    "local process."
                ),
            )

        def mutate_discussion(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[GroupDiscussionResult]:
            if not _can_run_discussion(record):
                raise InvestigationWorkflowConflictError(
                    "group discussion is unavailable in the latest state"
                )
            result = run_group_discussion(
                record.session,
                participant_bindings=record.runtime.participants,
                id_factory=record.runtime.id_factory,
                turn_count=record.runtime.capabilities.discussion_turns,
            )
            return InvestigationSessionMutation(
                session=result.session,
                result=result,
            )

        try:
            _updated_record, _discussion_result = registry.mutate(
                session_id,
                mutate_discussion,
            )
        except InvestigationSessionNotFoundError:
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message=(
                    "The requested investigation is not available in this "
                    "local process."
                ),
            )
        except InvestigationWorkflowConflictError:
            return render_error(
                request,
                status_code=409,
                page_title="Investigation conflict",
                heading="Group discussion could not run",
                message=(
                    "Group discussion cannot run in the investigation's "
                    "current workflow state. Refresh the session page and "
                    "try again."
                ),
            )
        except Exception:
            logger.exception("Local investigation discussion failed")
            return render_error(
                request,
                status_code=500,
                page_title="Investigation error",
                heading="Group discussion failed",
                message=(
                    "Group discussion could not be completed because of an "
                    "unexpected local generation error. The previous "
                    "investigation state was kept."
                ),
            )

        return RedirectResponse(
            url=f"/investigations/{session_id}",
            status_code=303,
        )

    @router.post(
        "/investigations/{session_id}/decision",
        response_class=HTMLResponse,
        name="create_investigation_decision",
    )
    async def create_investigation_decision(
        request: Request,
        session_id: str,
    ) -> Response:
        """Generate one complete current-round decision under the lock."""
        try:
            validate_run_id(session_id)
        except ValueError:
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message=(
                    "The requested investigation is not available in this "
                    "local process."
                ),
            )

        def mutate_decision(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[GroupDecisionResult]:
            if not _can_create_decision(record):
                raise InvestigationWorkflowConflictError(
                    "group decision is unavailable in the latest state"
                )
            result = create_group_decision(
                record.session,
                decision_provider=record.runtime.decision_provider,
                id_factory=record.runtime.id_factory,
            )
            return InvestigationSessionMutation(
                session=result.session,
                result=result,
            )

        try:
            _updated_record, _decision_result = registry.mutate(
                session_id,
                mutate_decision,
            )
        except InvestigationSessionNotFoundError:
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message=(
                    "The requested investigation is not available in this "
                    "local process."
                ),
            )
        except InvestigationWorkflowConflictError:
            return render_error(
                request,
                status_code=409,
                page_title="Investigation conflict",
                heading="Group decision could not be created",
                message=(
                    "A group decision cannot be created in the "
                    "investigation's current workflow state. Refresh the "
                    "session page and try again."
                ),
            )
        except Exception:
            logger.exception("Local investigation decision generation failed")
            return render_error(
                request,
                status_code=500,
                page_title="Investigation error",
                heading="Group decision failed",
                message=(
                    "The group decision could not be completed because of an "
                    "unexpected local generation error. The previous "
                    "investigation state was kept."
                ),
            )

        return RedirectResponse(
            url=f"/investigations/{session_id}",
            status_code=303,
        )

    @router.post(
        "/investigations/{session_id}/finalize",
        response_class=HTMLResponse,
        name="finalize_investigation_session",
    )
    async def finalize_investigation_session(
        request: Request,
        session_id: str,
    ) -> Response:
        """Explicitly generate and commit the Lead/Visit final theory."""
        try:
            validate_run_id(session_id)
        except ValueError:
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message=(
                    "The requested investigation is not available in this "
                    "local process."
                ),
            )

        def mutate_finalization(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[None]:
            session = record.session
            if session.status is not InvestigationStatus.ACTIVE:
                raise InvestigationWorkflowConflictError(
                    "Completed investigations cannot be finalized again."
                )
            if not session.visits or not session.revealed_information:
                raise InvestigationWorkflowConflictError(
                    "Presenting a final theory requires a visited lead and "
                    "revealed information."
                )
            result = finalize_lead_investigation(
                session,
                final_theory_provider=record.runtime.final_theory_provider,
                id_factory=record.runtime.id_factory,
            )
            return InvestigationSessionMutation(
                session=result.session,
                result=None,
            )

        try:
            registry.mutate(
                session_id,
                mutate_finalization,
            )
        except InvestigationSessionNotFoundError:
            return render_error(
                request,
                status_code=404,
                page_title="Investigation not found",
                heading="Investigation not found",
                message=(
                    "The requested investigation is not available in this "
                    "local process."
                ),
            )
        except InvestigationWorkflowConflictError as error:
            return render_error(
                request,
                status_code=409,
                page_title="Investigation conflict",
                heading="Investigation could not be finalized",
                message=str(error),
            )
        except Exception:
            logger.exception("Local investigation finalization failed")
            return render_error(
                request,
                status_code=500,
                page_title="Investigation error",
                heading="Investigation finalization failed",
                message=(
                    "The investigation could not be finalized because of an "
                    "unexpected local generation error. The previous "
                    "investigation state was kept."
                ),
            )

        return RedirectResponse(
            url=f"/investigations/{session_id}",
            status_code=303,
        )

    return router
    create_group_decision,
