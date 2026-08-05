"""Minimal FastAPI application for the local Sprint 4 interface."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from multi_agent_personalities.application import (
    ConversationResult,
    run_mock_conversation,
)
from multi_agent_personalities.models import Message
from multi_agent_personalities.pipeline import CharacterConfig, character_registry


WEB_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = PROJECT_ROOT / "outputs"
TEMPLATE_DIRECTORY = WEB_DIRECTORY / "templates"
STATIC_DIRECTORY = WEB_DIRECTORY / "static"
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)
logger = logging.getLogger(__name__)
_PALETTE_SIZE = 4
_ARTIFACT_DESCRIPTIONS = {
    "run.json": "Complete structured run metadata and messages.",
    "messages.jsonl": "One serialized message per line.",
    "transcript.md": "Human-readable Markdown transcript.",
}


@dataclass(frozen=True)
class CharacterPresentation:
    """Catalog-derived character data used only by the conversation UI."""

    slug: str
    character_id: str
    display_name: str
    description: str
    initials: str
    presentation_class: str
    selected: bool


@dataclass(frozen=True)
class MessagePresentation:
    """One message paired with identity-independent visual metadata."""

    message: Message
    initials: str
    presentation_class: str


def _display_initials(display_name: str) -> str:
    """Return deterministic initials from the first and last name words."""

    words = display_name.split()
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[-1][0]).upper()


def _character_presentations(
    registry: Mapping[str, CharacterConfig],
    selected_characters: Sequence[str],
) -> tuple[CharacterPresentation, ...]:
    selected = set(selected_characters)
    return tuple(
        CharacterPresentation(
            slug=config.slug,
            character_id=config.character_id,
            display_name=config.display_name,
            description=config.description,
            initials=_display_initials(config.display_name),
            presentation_class=f"participant-tone-{index % _PALETTE_SIZE + 1}",
            selected=config.slug in selected,
        )
        for index, config in enumerate(registry.values())
    )


def _message_presentations(
    messages: Sequence[Message],
    characters: Sequence[CharacterPresentation],
) -> tuple[MessagePresentation, ...]:
    presentation_by_id = {
        character.character_id: character for character in characters
    }
    presented: list[MessagePresentation] = []
    for message in messages:
        character = presentation_by_id.get(message.speaker_character_id)
        presented.append(
            MessagePresentation(
                message=message,
                initials=(
                    character.initials
                    if character is not None
                    else _display_initials(message.speaker_name)
                ),
                presentation_class=(
                    character.presentation_class
                    if character is not None
                    else "participant-tone-neutral"
                ),
            )
        )
    return tuple(presented)


def _repository_relative_path(path: Path, display_root: Path) -> str:
    """Format a trusted application-service path for local display."""
    return path.relative_to(display_root).as_posix()


def _validate_conversation_form(
    *,
    characters: list[str] | None,
    topic: str | None,
    turn_count: str | None,
    supported_characters: Sequence[str],
) -> tuple[list[str], str, int | None, dict[str, str], str, str]:
    """Validate form values and retain safe display values for re-rendering."""
    submitted_characters = list(characters or [])
    supported = set(supported_characters)
    selected_characters = [
        character for character in submitted_characters if character in supported
    ]
    raw_topic = topic or ""
    normalized_topic = raw_topic.strip()
    raw_turn_count = turn_count or ""
    field_errors: dict[str, str] = {}

    if len(submitted_characters) != len(set(submitted_characters)):
        field_errors["characters"] = "Select each available character only once."
    elif any(character not in supported for character in submitted_characters):
        field_errors["characters"] = "Select only currently available characters."
    elif len(submitted_characters) < 2:
        field_errors["characters"] = "Select at least two characters."

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
    registry: Mapping[str, CharacterConfig],
    display_root: Path,
    selected_characters: Sequence[str] | None = None,
    topic: str = "",
    turn_count: int | str = 6,
    conversation_result: ConversationResult | None = None,
    field_errors: Mapping[str, str] | None = None,
    error_message: str | None = None,
) -> dict[str, object]:
    """Build the shared template context for conversation pages."""
    resolved_selection = (
        tuple(registry) if selected_characters is None else selected_characters
    )
    available_characters = _character_presentations(
        registry,
        resolved_selection,
    )
    run_id: str | None = None
    artifact_directory_path: str | None = None
    artifact_files: tuple[dict[str, str], ...] = ()
    if conversation_result is not None:
        run_id = conversation_result.run_id
        artifact_directory_path = _repository_relative_path(
            conversation_result.artifact_directory,
            display_root,
        )
        artifact_files = tuple(
            {
                "filename": artifact_path.name,
                "description": _ARTIFACT_DESCRIPTIONS[artifact_path.name],
                "path": _repository_relative_path(artifact_path, display_root),
            }
            for artifact_path in conversation_result.artifact_paths
        )

    return {
        "page_title": "Multi-Agent Fictional Personalities",
        "provider_name": "mock",
        "available_characters": available_characters,
        "topic_value": topic,
        "turn_count_value": turn_count,
        "conversation_result": conversation_result,
        "message_presentations": (
            _message_presentations(
                conversation_result.run.messages,
                available_characters,
            )
            if conversation_result is not None
            else ()
        ),
        "run_id": run_id,
        "artifact_directory_path": artifact_directory_path,
        "artifact_files": artifact_files,
        "field_errors": dict(field_errors or {}),
        "error_message": error_message,
    }


def _render_page(
    request: Request,
    *,
    registry: Mapping[str, CharacterConfig],
    display_root: Path,
    status_code: int = 200,
    **context_values: object,
) -> HTMLResponse:
    """Render the shared interface with an explicit response status."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=_page_context(
            registry=registry,
            display_root=display_root,
            **context_values,
        ),
        status_code=status_code,
    )


def create_app(
    *,
    project_root: Path | None = None,
    output_root: Path | None = None,
) -> FastAPI:
    """Create the local web application without starting a server."""
    resolved_project_root = (
        PROJECT_ROOT if project_root is None else Path(project_root)
    )
    resolved_output_root = (
        OUTPUT_ROOT if output_root is None else Path(output_root)
    )
    registry = character_registry(resolved_project_root)
    supported_characters = tuple(registry)
    display_root = resolved_output_root.parent
    application = FastAPI(
        title="Multi-Agent Fictional Personalities",
        description=(
            "Local mock conversation interface for fictional detective agents."
        ),
        version="0.1.0",
    )
    @application.get("/static/{path:path}", name="static")
    async def static_asset(path: str) -> Response:
        """Serve the two fixed local assets without a worker-thread hop."""
        media_types = {
            "styles.css": "text/css",
            "conversation.js": "text/javascript",
        }
        if path not in media_types:
            return Response(status_code=404)
        return Response(
            content=(STATIC_DIRECTORY / path).read_bytes(),
            media_type=media_types[path],
        )

    @application.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        """Render the static conversation workspace."""
        return _render_page(
            request,
            registry=registry,
            display_root=display_root,
        )

    @application.post(
        "/conversations",
        response_class=HTMLResponse,
        name="start_conversation",
    )
    async def start_conversation(
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
            supported_characters=supported_characters,
        )
        if field_errors:
            return _render_page(
                request,
                registry=registry,
                display_root=display_root,
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
                output_root=resolved_output_root,
                project_root=resolved_project_root,
            )
        except FileExistsError:
            logger.exception("Conversation run identifier collision")
            return _render_page(
                request,
                registry=registry,
                display_root=display_root,
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
                registry=registry,
                display_root=display_root,
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
                registry=registry,
                display_root=display_root,
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
            registry=registry,
            display_root=display_root,
            selected_characters=selected_characters,
            topic=normalized_topic,
            turn_count=parsed_turn_count,
            conversation_result=result,
        )

    @application.get("/health")
    async def health() -> dict[str, str]:
        """Report local application availability without external calls."""
        return {"status": "ok", "provider": "mock"}

    return application


app = create_app()
