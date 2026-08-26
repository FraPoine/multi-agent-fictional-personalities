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
)
from multi_agent_personalities.models import validate_run_id
from multi_agent_personalities.pipeline import CharacterConfig
from multi_agent_personalities.web.investigation_store import (
    InMemoryInvestigationRegistry,
    InvestigationRegistryInvariantError,
    InvestigationSessionCollisionError,
    InvestigationSessionNotFoundError,
    InvestigationSessionRecord,
)


MAX_CASE_INTRODUCTION_LENGTH = 4000
logger = logging.getLogger(__name__)


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


def _workflow_state(record: InvestigationSessionRecord) -> str:
    if not record.session.rounds:
        return "Awaiting first clue"
    return record.session.rounds[-1].status.value.replace("_", " ").title()


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
            return templates.TemplateResponse(
                request=request,
                name="investigation_error.html",
                context={
                    "page_title": "Investigation not found",
                    "provider_name": "mock",
                    "message": (
                        "The requested investigation is not available in this "
                        "local process."
                    ),
                },
                status_code=404,
            )

        return templates.TemplateResponse(
            request=request,
            name="investigation_detail.html",
            context={
                "page_title": "Investigation session",
                "provider_name": "mock",
                "record": record,
                "workflow_state": _workflow_state(record),
            },
            status_code=200,
        )

    return router
