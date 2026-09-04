"""Server-rendered Lead/Visit investigation routes."""

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from multi_agent_personalities.application import (
    CurrentCaseLeadConflictError,
    ConclusionConflictError,
    DeterministicAnswerDraftProvider,
    GameplayConflictError,
    InvalidCaseLeadReferenceError,
    InvestigationMockCapabilities,
    ResourceConsultationError,
    UnknownCaseLeadReferenceError,
    UnknownConsultationResourceError,
    complete_case_interaction,
    confirm_official_score,
    consult_case_resource,
    continue_lead_discussion,
    disclose_case_sections,
    finalize_lead_investigation,
    generate_official_answer_drafts,
    investigation_mock_capabilities,
    lock_official_answers,
    reveal_manual_information,
    reveal_official_answer_elements,
    reveal_official_solution,
    reveal_information,
    revisit_playable_case_lead,
    start_official_conclusion,
    update_official_answer,
    visit_case_lead,
    visit_lead,
    visit_playable_case_lead,
)
from multi_agent_personalities.case_catalog import (
    CaseCatalog,
    default_case_catalog_directory,
)
from multi_agent_personalities.models import InvestigationStatus, validate_run_id
from multi_agent_personalities.conclusion_catalog import (
    PrivateScoringRepository,
    PrivateSolutionRepository,
    default_private_scoring_directory,
    default_private_solution_directory,
)
from multi_agent_personalities.pipeline import CharacterConfig
from multi_agent_personalities.web.investigation_presentation import (
    catalogue_participants,
    present_session,
)
from multi_agent_personalities.web.investigation_store import (
    InMemoryInvestigationRegistry,
    InvestigationRegistryInvariantError,
    InvestigationSessionCollisionError,
    InvestigationSessionMutation,
    InvestigationSessionNotFoundError,
    InvestigationSessionRecord,
)


MAX_LEAD_REFERENCE_LENGTH = 80
MAX_INFORMATION_LENGTH = 4000
MIN_INVESTIGATORS = 2
logger = logging.getLogger(__name__)


class InvestigationWorkflowConflictError(ValueError):
    """Raised when an action conflicts with the latest immutable snapshot."""


class InvestigationResourceNotFoundError(ValueError):
    """Raised when a session-scoped Lead/Visit resource is unknown."""


@dataclass(frozen=True)
class InvestigationCharacterPresentation:
    """Catalogue identity paired with form-selection state."""

    config: CharacterConfig
    selected: bool


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
    known_slugs: Sequence[str],
    supported_slugs: Sequence[str],
) -> tuple[list[str], dict[str, str]]:
    """Validate user-controlled fields before runtime/session construction."""
    submitted = list(characters or [])
    known = set(known_slugs)
    supported = set(supported_slugs)
    selected = [slug for slug in submitted if slug in supported]
    errors: dict[str, str] = {}

    if len(submitted) != len(set(submitted)):
        errors["characters"] = "Select each investigator only once."
    elif any(slug not in known for slug in submitted):
        errors["characters"] = "Select only characters in the current catalogue."
    elif any(slug not in supported for slug in submitted):
        errors["characters"] = (
            "Select only investigators supported by the current mock scenario."
        )
    elif len(submitted) < MIN_INVESTIGATORS:
        errors["characters"] = "Select all supported investigators."
    elif set(submitted) != supported:
        errors["characters"] = (
            "Select the complete investigator set required by the mock scenario."
        )

    return selected, errors


def _selectable_cases(
    *,
    registry: InMemoryInvestigationRegistry,
    case_catalog: CaseCatalog,
    include_compatibility_cases: bool,
):
    """Return the single authoritative web case-creation policy."""
    if include_compatibility_cases:
        return case_catalog.cases
    return tuple(
        case
        for case in case_catalog.cases
        if registry.case_content_catalog is None
        or not registry.case_content_catalog.cases
        or registry.case_content_catalog.get(case.case_id) is not None
    )


def _index_context(
    *,
    registry: InMemoryInvestigationRegistry,
    catalogue: Mapping[str, CharacterConfig],
    supported_configs: Sequence[CharacterConfig],
    capabilities: InvestigationMockCapabilities,
    case_catalog: CaseCatalog,
    selected_slugs: Sequence[str] | None = None,
    selected_case_id: str | None = None,
    field_errors: Mapping[str, str] | None = None,
    error_message: str | None = None,
    include_compatibility_cases: bool = False,
) -> dict[str, object]:
    selected = (
        {item.slug for item in supported_configs}
        if selected_slugs is None
        else set(selected_slugs)
    )
    resolved_case_id = (
        case_catalog.cases[0].case_id
        if selected_case_id is None
        else selected_case_id
    )
    required_investigators = {item.slug for item in supported_configs}
    selectable_cases = _selectable_cases(
        registry=registry,
        case_catalog=case_catalog,
        include_compatibility_cases=include_compatibility_cases,
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
        "cases": selectable_cases,
        "selected_case_id": resolved_case_id,
        "case_titles": {
            case.case_id: case.title for case in selectable_cases
        },
        "capabilities": capabilities,
        "minimum_investigators": MIN_INVESTIGATORS,
        "required_investigator_count": len(required_investigators),
        "creation_ready": (
            resolved_case_id in {case.case_id for case in selectable_cases}
            and selected == required_investigators
            and len(selected) >= MIN_INVESTIGATORS
        ),
        "field_errors": dict(field_errors or {}),
        "error_message": error_message,
        "existing_records": tuple(
            registry.get(session_id) for session_id in registry.session_ids
        ),
    }


def create_investigation_router(
    *,
    registry: InMemoryInvestigationRegistry,
    project_root: Path,
    catalogue: Mapping[str, CharacterConfig],
    case_catalog: CaseCatalog,
    templates: Jinja2Templates,
    include_compatibility_cases: bool = False,
) -> APIRouter:
    """Create the authoritative Lead/Visit browser router."""
    router = APIRouter()
    capabilities = investigation_mock_capabilities()
    supported_configs = _supported_configs(catalogue, capabilities)
    known_slugs = tuple(catalogue)
    supported_slugs = tuple(config.slug for config in supported_configs)
    selectable_cases = _selectable_cases(
        registry=registry,
        case_catalog=case_catalog,
        include_compatibility_cases=include_compatibility_cases,
    )
    selectable_cases_by_id = {case.case_id: case for case in selectable_cases}
    scoring_repository = PrivateScoringRepository(default_private_scoring_directory(project_root))
    solution_repository = PrivateSolutionRepository(default_private_solution_directory(project_root))

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
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="investigation_detail.html",
            context={
                "page_title": "Investigation session",
                "provider_name": "mock",
                "investigation": present_session(
                    record,
                    case_catalog=case_catalog,
                    resource_base_directory=(
                        default_case_catalog_directory(project_root).parent
                    ),
                    selected_lead_id=selected_lead_id,
                    case_content_catalog=registry.case_content_catalog,
                    resource_text_catalog=registry.resource_text_catalog,
                    public_conclusion_catalog=registry.public_conclusion_catalog,
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
                case_catalog=case_catalog,
                include_compatibility_cases=include_compatibility_cases,
                **context,
            ),
            status_code=status_code,
        )

    def resource_error(
        request: Request,
        *,
        status_code: int,
        heading: str,
        message: str,
    ) -> HTMLResponse:
        return render_error(
            request,
            status_code=status_code,
            page_title=(
                "Investigation conflict"
                if status_code == 409
                else "Investigation resource not found"
            ),
            heading=heading,
            message=message,
        )

    def require_current_visit(
        record: InvestigationSessionRecord,
        visit_id: str,
    ) -> None:
        if record.session.status is not InvestigationStatus.ACTIVE:
            raise InvestigationWorkflowConflictError(
                "Completed investigations are read-only."
            )
        if record.session.case_state and record.session.case_state.outcome:
            raise InvestigationWorkflowConflictError("This case has ended and is read-only.")
        if not any(item.visit_id == visit_id for item in record.session.visits):
            raise InvestigationResourceNotFoundError(visit_id)
        if record.session.visits[-1].visit_id != visit_id:
            raise InvestigationWorkflowConflictError(
                "This historical visit is read-only. Revisit its lead explicitly."
            )

    def execute_mutation(
        request: Request,
        session_id: str,
        operation: Callable[
            [InvestigationSessionRecord],
            InvestigationSessionMutation[Any],
        ],
        *,
        failure_heading: str,
    ) -> tuple[InvestigationSessionRecord, Any] | Response:
        try:
            return registry.mutate(session_id, operation)
        except (
            InvestigationSessionNotFoundError,
            InvestigationResourceNotFoundError,
        ):
            return resource_error(
                request,
                status_code=404,
                heading="Investigation resource not found",
                message="The requested session resource is not available.",
            )
        except InvalidCaseLeadReferenceError as error:
            return render_error(
                request,
                status_code=400,
                page_title="Invalid lead reference",
                heading=failure_heading,
                message=str(error),
            )
        except UnknownCaseLeadReferenceError as error:
            return resource_error(
                request,
                status_code=404,
                heading=failure_heading,
                message=str(error),
            )
        except CurrentCaseLeadConflictError as error:
            return resource_error(
                request,
                status_code=409,
                heading=failure_heading,
                message=str(error),
            )
        except (UnknownConsultationResourceError, KeyError):
            return resource_error(
                request,
                status_code=404,
                heading=failure_heading,
                message="The requested case resource is not available.",
            )
        except (
            InvestigationWorkflowConflictError,
            GameplayConflictError,
            ResourceConsultationError,
            ConclusionConflictError,
        ) as error:
            return resource_error(
                request,
                status_code=409,
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

    @router.get(
        "/investigations",
        response_class=HTMLResponse,
        name="investigations_index",
    )
    async def investigations_index(request: Request) -> HTMLResponse:
        return render_index(request)

    @router.post(
        "/investigations",
        response_class=HTMLResponse,
        name="create_investigation",
    )
    async def create_investigation(
        request: Request,
        characters: Annotated[list[str] | None, Form()] = None,
        case_id: Annotated[str | None, Form()] = None,
    ) -> Response:
        if case_id is not None:
            try:
                selected_case = selectable_cases_by_id[case_id]
            except KeyError:
                return render_error(
                    request,
                    status_code=404,
                    page_title="Case not found",
                    heading="Case not found",
                    message="The selected local case is not available.",
                )
        else:
            selected_case = None
        selected, field_errors = _validate_investigation_creation_form(
            characters=characters,
            known_slugs=known_slugs,
            supported_slugs=supported_slugs,
        )
        if selected_case is None:
            field_errors["case_id"] = "Select one available case."
        if field_errors:
            return render_index(
                request,
                status_code=400,
                selected_slugs=selected,
                selected_case_id=case_id,
                field_errors=field_errors,
                error_message="Correct the highlighted fields and try again.",
            )
        if selected_case is None:
            raise RuntimeError("validated case selection is unexpectedly missing")
        try:
            creation_case = (
                {"case_id": selected_case.case_id}
                if registry.case_catalog is case_catalog
                else {"case_definition": selected_case}
            )
            record = registry.create(
                character_slugs=selected,
                project_root=project_root,
                **creation_case,
            )
        except InvestigationSessionCollisionError:
            logger.exception("Investigation session identifier collision")
            return render_index(
                request,
                status_code=409,
                selected_slugs=selected,
                selected_case_id=selected_case.case_id,
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
                selected_case_id=selected_case.case_id,
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
            return resource_error(
                request,
                status_code=404,
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
        reference: Annotated[str | None, Form()] = None,
        mode: Annotated[str | None, Form()] = None,
    ) -> Response:
        raw_reference = reference or ""
        if not raw_reference.strip() or len(raw_reference) > MAX_LEAD_REFERENCE_LENGTH:
            return render_error(
                request,
                status_code=400,
                page_title="Invalid lead",
                heading="Lead could not be visited",
                message="Enter a case lead reference within the displayed limit.",
            )

        def mutate(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[str]:
            if record.session.status is not InvestigationStatus.ACTIVE:
                raise InvestigationWorkflowConflictError(
                    "Completed investigations are read-only."
                )
            try:
                case_definition = case_catalog.get(record.session.case_id)
            except KeyError as error:
                raise InvestigationResourceNotFoundError(
                    record.session.case_id
                ) from error
            content = registry.case_content_catalog.get(record.session.case_id) if registry.case_content_catalog else None
            result = (
                visit_playable_case_lead(record.session, case_definition=case_definition, case_content=content, id_factory=record.runtime.id_factory, raw_reference=raw_reference, mode=(mode or None))
                if content is not None else
                visit_case_lead(record.session, case_definition=case_definition, id_factory=record.runtime.id_factory, raw_reference=raw_reference)
            )
            return InvestigationSessionMutation(
                session=result.session,
                result=result.lead.lead_id,
            )

        result = execute_mutation(
            request,
            session_id,
            mutate,
            failure_heading="Lead could not be visited",
        )
        if isinstance(result, Response):
            return result
        _record, lead_id = result
        return RedirectResponse(
            url=f"/investigations/{session_id}?lead={lead_id}",
            status_code=303,
        )

    @router.post(
        "/investigations/{session_id}/leads/{lead_id}/visit",
        response_class=HTMLResponse,
        name="revisit_investigation_lead",
    )
    async def revisit_investigation_lead(
        request: Request,
        session_id: str,
        lead_id: str,
        mode: Annotated[str | None, Form()] = None,
    ) -> Response:
        def mutate(
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
                    "The selected lead is already current."
                )
            content = registry.case_content_catalog.get(record.session.case_id) if registry.case_content_catalog else None
            updated = (
                revisit_playable_case_lead(record.session, case_content=content, lead_id=lead_id, mode=(mode or None), id_factory=record.runtime.id_factory)
                if content is not None else
                visit_lead(record.session, id_factory=record.runtime.id_factory, lead_id=lead_id, mode=(mode or None))
            )
            return InvestigationSessionMutation(session=updated, result=None)

        result = execute_mutation(
            request,
            session_id,
            mutate,
            failure_heading="Lead could not be revisited",
        )
        if isinstance(result, Response):
            return result
        return RedirectResponse(
            url=f"/investigations/{session_id}?lead={lead_id}",
            status_code=303,
        )

    @router.post(
        "/investigations/{session_id}/visits/{visit_id}/interaction",
        response_class=HTMLResponse,
        name="complete_investigation_interaction",
    )
    async def complete_investigation_interaction(
        request: Request, session_id: str, visit_id: str,
        interaction_id: Annotated[str, Form()], option_id: Annotated[str | None, Form()] = None,
    ) -> Response:
        def mutate(record: InvestigationSessionRecord) -> InvestigationSessionMutation[None]:
            require_current_visit(record, visit_id)
            content = registry.case_content_catalog.get(record.session.case_id) if registry.case_content_catalog else None
            if content is None: raise InvestigationWorkflowConflictError("This case has no preloaded interaction.")
            updated = complete_case_interaction(record.session, case_content=content, visit_id=visit_id, interaction_id=interaction_id, option_id=option_id, id_factory=record.runtime.id_factory)
            return InvestigationSessionMutation(session=updated, result=None)
        result = execute_mutation(request, session_id, mutate, failure_heading="Interaction could not be completed")
        if isinstance(result, Response): return result
        record, _ = result
        return RedirectResponse(url=f"/investigations/{session_id}?lead={record.session.visits[-1].lead_id}", status_code=303)

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

        def mutate(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[None]:
            require_current_visit(record, visit_id)
            content = registry.case_content_catalog.get(record.session.case_id) if registry.case_content_catalog else None
            updated = reveal_manual_information(
                record.session,
                case_content=content,
                visit_id=visit_id,
                information_texts=(normalized,),
                id_factory=record.runtime.id_factory,
            )
            return InvestigationSessionMutation(session=updated, result=None)

        result = execute_mutation(
            request,
            session_id,
            mutate,
            failure_heading="Information could not be added",
        )
        if isinstance(result, Response):
            return result
        record, _ = result
        return RedirectResponse(
            url=(
                f"/investigations/{session_id}"
                f"?lead={record.session.visits[-1].lead_id}"
            ),
            status_code=303,
        )

    @router.post(
        "/investigations/{session_id}/visits/{visit_id}/discussion",
        response_class=HTMLResponse,
        name="continue_visit_discussion",
    )
    async def continue_visit_discussion(
        request: Request,
        session_id: str,
        visit_id: str,
    ) -> Response:
        def mutate(
            record: InvestigationSessionRecord,
        ) -> InvestigationSessionMutation[None]:
            require_current_visit(record, visit_id)
            result = continue_lead_discussion(
                record.session,
                visit_id=visit_id,
                participant_bindings=record.runtime.participants,
                id_factory=record.runtime.id_factory,
                turn_count=record.runtime.capabilities.discussion_turns,
                resource_text_catalog=registry.resource_text_catalog,
            )
            return InvestigationSessionMutation(session=result.session, result=None)

        result = execute_mutation(
            request,
            session_id,
            mutate,
            failure_heading="Discussion could not continue",
        )
        if isinstance(result, Response):
            return result
        record, _ = result
        return RedirectResponse(
            url=(
                f"/investigations/{session_id}"
                f"?lead={record.session.visits[-1].lead_id}"
            ),
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
        def mutate(
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
            return InvestigationSessionMutation(session=result.session, result=None)

        result = execute_mutation(
            request,
            session_id,
            mutate,
            failure_heading="Investigation could not be finalized",
        )
        if isinstance(result, Response):
            return result
        return RedirectResponse(
            url=f"/investigations/{session_id}",
            status_code=303,
        )

    @router.post(
        "/investigations/{session_id}/resources/{resource_id}/consult",
        response_class=HTMLResponse,
        name="consult_investigation_resource",
    )
    async def consult_investigation_resource(request: Request, session_id: str, resource_id: str) -> Response:
        def mutate(record: InvestigationSessionRecord) -> InvestigationSessionMutation[None]:
            if registry.resource_text_catalog is None:
                raise InvestigationWorkflowConflictError("Verified resource text is unavailable.")
            updated = consult_case_resource(
                record.session, resource_id=resource_id, case_catalog=case_catalog,
                resource_text_catalog=registry.resource_text_catalog,
            )
            return InvestigationSessionMutation(session=updated, result=None)
        result = execute_mutation(request, session_id, mutate, failure_heading="Resource could not be consulted")
        if isinstance(result, Response): return result
        return RedirectResponse(url=f"/investigations/{session_id}", status_code=303)

    @router.post("/investigations/{session_id}/conclusion/start", response_class=HTMLResponse, name="start_investigation_conclusion")
    async def start_investigation_conclusion(request: Request, session_id: str) -> Response:
        def mutate(record: InvestigationSessionRecord) -> InvestigationSessionMutation[None]:
            public = registry.public_conclusion_catalog.get(record.session.case_id) if registry.public_conclusion_catalog else None
            if public is None: raise InvestigationWorkflowConflictError("This case has no official-question conclusion.")
            return InvestigationSessionMutation(session=start_official_conclusion(record.session, public_definition=public), result=None)
        result = execute_mutation(request, session_id, mutate, failure_heading="Conclusion could not be started")
        if isinstance(result, Response): return result
        return RedirectResponse(url=f"/investigations/{session_id}", status_code=303)

    @router.post("/investigations/{session_id}/conclusion/drafts", response_class=HTMLResponse, name="generate_investigation_conclusion_drafts")
    async def generate_investigation_conclusion_drafts(request: Request, session_id: str) -> Response:
        def mutate(record: InvestigationSessionRecord) -> InvestigationSessionMutation[None]:
            public = registry.public_conclusion_catalog.get(record.session.case_id) if registry.public_conclusion_catalog else None
            if public is None: raise InvestigationWorkflowConflictError("Public questions are unavailable.")
            provider = DeterministicAnswerDraftProvider({question.question_id: f"Investigator draft for {question.question_id}." for question in public.questions})
            result = generate_official_answer_drafts(
                record.session, public_definition=public, provider=provider,
                resource_text_catalog=registry.resource_text_catalog,
            )
            return InvestigationSessionMutation(session=result.session, result=None)
        result = execute_mutation(request, session_id, mutate, failure_heading="Answer drafts could not be generated")
        if isinstance(result, Response): return result
        return RedirectResponse(url=f"/investigations/{session_id}", status_code=303)

    @router.post("/investigations/{session_id}/conclusion/answers/{question_id}", response_class=HTMLResponse, name="edit_investigation_conclusion_answer")
    async def edit_investigation_conclusion_answer(request: Request, session_id: str, question_id: str, answer: Annotated[str | None, Form()] = None) -> Response:
        if answer is None or not answer.strip() or len(answer) > MAX_INFORMATION_LENGTH:
            return render_error(request, status_code=400, page_title="Invalid answer", heading="Answer could not be saved", message="Enter a non-empty answer within the displayed limit.")
        def mutate(record: InvestigationSessionRecord) -> InvestigationSessionMutation[None]:
            return InvestigationSessionMutation(session=update_official_answer(record.session, question_id=question_id, text=answer.strip()), result=None)
        result = execute_mutation(request, session_id, mutate, failure_heading="Answer could not be saved")
        if isinstance(result, Response): return result
        return RedirectResponse(url=f"/investigations/{session_id}", status_code=303)

    @router.post("/investigations/{session_id}/conclusion/lock", response_class=HTMLResponse, name="lock_investigation_conclusion_answers")
    async def lock_investigation_conclusion_answers(request: Request, session_id: str) -> Response:
        def mutate(record: InvestigationSessionRecord) -> InvestigationSessionMutation[None]:
            return InvestigationSessionMutation(session=lock_official_answers(record.session), result=None)
        result = execute_mutation(request, session_id, mutate, failure_heading="Answers could not be locked")
        if isinstance(result, Response): return result
        return RedirectResponse(url=f"/investigations/{session_id}", status_code=303)

    @router.post("/investigations/{session_id}/conclusion/answer-elements", response_class=HTMLResponse, name="reveal_investigation_answer_elements")
    async def reveal_investigation_answer_elements(request: Request, session_id: str) -> Response:
        def mutate(record: InvestigationSessionRecord) -> InvestigationSessionMutation[None]:
            return InvestigationSessionMutation(session=reveal_official_answer_elements(record.session, repository=scoring_repository), result=None)
        result = execute_mutation(request, session_id, mutate, failure_heading="Official answer elements could not be revealed")
        if isinstance(result, Response): return result
        return RedirectResponse(url=f"/investigations/{session_id}", status_code=303)

    @router.post("/investigations/{session_id}/conclusion/score", response_class=HTMLResponse, name="score_investigation_conclusion")
    async def score_investigation_conclusion(request: Request, session_id: str, awarded_element: Annotated[list[str] | None, Form()] = None) -> Response:
        selected = tuple(awarded_element or ())
        def mutate(record: InvestigationSessionRecord) -> InvestigationSessionMutation[None]:
            conclusion = record.session.conclusion
            if conclusion is None: raise ConclusionConflictError("Official conclusion is not active.")
            by_id = {element.element_id: element for element in conclusion.answer_elements}
            if any(element_id not in by_id for element_id in selected):
                raise ConclusionConflictError("Unknown official answer element.")
            awards: dict[str, list[str]] = {}
            for element_id in selected:
                awards.setdefault(by_id[element_id].question_id, []).append(element_id)
            return InvestigationSessionMutation(session=confirm_official_score(record.session, awarded_elements=awards), result=None)
        result = execute_mutation(request, session_id, mutate, failure_heading="Score could not be confirmed")
        if isinstance(result, Response): return result
        return RedirectResponse(url=f"/investigations/{session_id}", status_code=303)

    @router.post("/investigations/{session_id}/conclusion/solution", response_class=HTMLResponse, name="reveal_investigation_solution")
    async def reveal_investigation_solution(request: Request, session_id: str) -> Response:
        def mutate(record: InvestigationSessionRecord) -> InvestigationSessionMutation[None]:
            return InvestigationSessionMutation(session=reveal_official_solution(record.session, repository=solution_repository), result=None)
        result = execute_mutation(request, session_id, mutate, failure_heading="Official solution could not be revealed")
        if isinstance(result, Response): return result
        return RedirectResponse(url=f"/investigations/{session_id}", status_code=303)

    return router
