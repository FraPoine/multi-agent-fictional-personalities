"""Server-rendered investigation creation and canonical session routes."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from multi_agent_personalities.application import (
    InvestigationMockCapabilities,
    investigation_mock_capabilities,
    reveal_clue,
)
from multi_agent_personalities.models import (
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


MAX_CASE_INTRODUCTION_LENGTH = 4000
MAX_CLUE_LENGTH = 4000
logger = logging.getLogger(__name__)


class InvestigationWorkflowConflictError(ValueError):
    """Raised when a browser action conflicts with the latest snapshot."""


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
    return tuple(
        by_id[participant_id]
        for participant_id in capabilities.participant_ids
        if participant_id in by_id
    )


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
                "record": record,
                "workflow_state": _workflow_state(record),
                "workflow_message": _workflow_message(record),
                "can_reveal_clue": _can_reveal_clue(record),
                "clue_value": clue_value,
                "clue_error": clue_error,
                "max_clue_length": MAX_CLUE_LENGTH,
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

        return render_detail(request, record)

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
            if (
                len(record.session.rounds)
                >= record.runtime.capabilities.supported_rounds
            ):
                raise InvestigationWorkflowConflictError(
                    "mock clue-round capability exhausted"
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
        except (InvestigationWorkflowConflictError, ValueError):
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

    return router
