"""Minimal FastAPI application for the local Sprint 4 interface."""

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from multi_agent_personalities.application import (
    ConversationResult,
    run_mock_conversation,
)


WEB_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = PROJECT_ROOT / "outputs"
TEMPLATE_DIRECTORY = WEB_DIRECTORY / "templates"
STATIC_DIRECTORY = WEB_DIRECTORY / "static"
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
logger = logging.getLogger(__name__)
_SUPPORTED_CHARACTERS = ("sherlock", "poirot")
_ARTIFACT_DESCRIPTIONS = {
    "run.json": "Complete structured run metadata and messages.",
    "messages.jsonl": "One serialized message per line.",
    "transcript.md": "Human-readable Markdown transcript.",
}


def _repository_relative_path(path: Path) -> str:
    """Format a trusted application-service path for local display."""
    return path.relative_to(PROJECT_ROOT).as_posix()


def _validate_conversation_form(
    *,
    characters: list[str] | None,
    topic: str | None,
    turn_count: str | None,
) -> tuple[list[str], str, int | None, dict[str, str], str, str]:
    """Validate form values and retain safe display values for re-rendering."""
    submitted_characters = list(characters or [])
    selected_characters = [
        character
        for character in submitted_characters
        if character in _SUPPORTED_CHARACTERS
    ]
    raw_topic = topic or ""
    normalized_topic = raw_topic.strip()
    raw_turn_count = turn_count or ""
    field_errors: dict[str, str] = {}

    if (
        len(submitted_characters) != len(set(submitted_characters))
        or any(
            character not in _SUPPORTED_CHARACTERS
            for character in submitted_characters
        )
    ):
        field_errors["characters"] = (
            "Select each supported detective only once."
        )
    elif (
        len(submitted_characters) < 2
        or set(submitted_characters) != set(_SUPPORTED_CHARACTERS)
    ):
        field_errors["characters"] = (
            "Select both Sherlock Holmes and Hercule Poirot."
        )

    if not normalized_topic:
        field_errors["topic"] = "Enter an investigation topic."

    parsed_turn_count: int | None = None
    normalized_turn_count = raw_turn_count.strip()
    if normalized_turn_count.isascii() and normalized_turn_count.isdecimal():
        try:
            parsed_turn_count = int(normalized_turn_count)
        except ValueError:
            pass
    if parsed_turn_count is None or not 2 <= parsed_turn_count <= 12:
        field_errors["turn_count"] = (
            "Enter a whole number between 2 and 12."
        )

    return (
        selected_characters,
        normalized_topic,
        parsed_turn_count,
        field_errors,
        raw_topic,
        raw_turn_count,
    )


def _page_context(
    *,
    selected_characters: Sequence[str] = ("sherlock", "poirot"),
    topic: str = "",
    turn_count: int | str = 6,
    conversation_result: ConversationResult | None = None,
    field_errors: Mapping[str, str] | None = None,
    error_message: str | None = None,
) -> dict[str, object]:
    """Build the shared template context for conversation pages."""
    run_id: str | None = None
    artifact_directory_path: str | None = None
    artifact_files: tuple[dict[str, str], ...] = ()
    if conversation_result is not None:
        run_id = conversation_result.run_id
        artifact_directory_path = _repository_relative_path(
            conversation_result.artifact_directory
        )
        artifact_files = tuple(
            {
                "filename": artifact_path.name,
                "description": _ARTIFACT_DESCRIPTIONS[artifact_path.name],
                "path": _repository_relative_path(artifact_path),
            }
            for artifact_path in conversation_result.artifact_paths
        )

    return {
        "page_title": "Multi-Agent Fictional Personalities",
        "provider_name": "mock",
        "selected_characters": selected_characters,
        "topic_value": topic,
        "turn_count_value": turn_count,
        "conversation_result": conversation_result,
        "run_id": run_id,
        "artifact_directory_path": artifact_directory_path,
        "artifact_files": artifact_files,
        "field_errors": dict(field_errors or {}),
        "error_message": error_message,
    }


def _render_page(
    request: Request,
    *,
    status_code: int = 200,
    **context_values: object,
) -> HTMLResponse:
    """Render the shared interface with an explicit response status."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=_page_context(**context_values),
        status_code=status_code,
    )


def create_app() -> FastAPI:
    """Create the local web application without starting a server."""
    application = FastAPI(
        title="Multi-Agent Fictional Personalities",
        description=(
            "Local mock conversation interface for fictional detective agents."
        ),
        version="0.1.0",
    )
    application.mount(
        "/static",
        StaticFiles(directory=STATIC_DIRECTORY),
        name="static",
    )

    @application.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        """Render the static conversation workspace."""
        return _render_page(request)

    @application.post(
        "/conversations",
        response_class=HTMLResponse,
        name="start_conversation",
    )
    def start_conversation(
        request: Request,
        characters: Annotated[list[str] | None, Form()] = None,
        topic: Annotated[str | None, Form()] = None,
        turn_count: Annotated[str | None, Form()] = None,
    ) -> HTMLResponse:
        """Run and persist a deterministic mock conversation."""
        (
            selected_characters,
            normalized_topic,
            parsed_turn_count,
            field_errors,
            topic_value,
            turn_count_value,
        ) = _validate_conversation_form(
            characters=characters,
            topic=topic,
            turn_count=turn_count,
        )
        if field_errors:
            return _render_page(
                request,
                status_code=400,
                selected_characters=selected_characters,
                topic=topic_value,
                turn_count=turn_count_value,
                field_errors=field_errors,
                error_message=(
                    "Please correct the highlighted fields and submit again."
                ),
            )

        if parsed_turn_count is None:
            raise RuntimeError("validated turn count is unexpectedly missing")

        try:
            result = run_mock_conversation(
                character_slugs=selected_characters,
                topic=normalized_topic,
                turn_count=parsed_turn_count,
                seed=42,
                output_root=OUTPUT_ROOT,
                project_root=PROJECT_ROOT,
            )
        except FileExistsError:
            logger.exception("Conversation run identifier collision")
            return _render_page(
                request,
                status_code=409,
                selected_characters=selected_characters,
                topic=normalized_topic,
                turn_count=parsed_turn_count,
                error_message=(
                    "A run with the generated identifier already exists. "
                    "Submit the conversation again."
                ),
            )
        except OSError:
            logger.exception("Conversation persistence failed")
            return _render_page(
                request,
                status_code=500,
                selected_characters=selected_characters,
                topic=normalized_topic,
                turn_count=parsed_turn_count,
                error_message=(
                    "The conversation could not be saved. Check that the "
                    "outputs directory is writable and try again."
                ),
            )
        except ValueError:
            logger.exception("Local mock conversation generation failed")
            return _render_page(
                request,
                status_code=500,
                selected_characters=selected_characters,
                topic=normalized_topic,
                turn_count=parsed_turn_count,
                error_message=(
                    "The local mock conversation could not be generated. "
                    "Check the project fixtures and try again."
                ),
            )

        return _render_page(
            request,
            selected_characters=selected_characters,
            topic=normalized_topic,
            turn_count=parsed_turn_count,
            conversation_result=result,
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        """Report local application availability without external calls."""
        return {"status": "ok", "provider": "mock"}

    return application


app = create_app()
