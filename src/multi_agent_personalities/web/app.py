"""Minimal FastAPI application for the local Sprint 4 interface."""

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
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


def _page_context(
    *,
    selected_characters: Sequence[str] = ("sherlock", "poirot"),
    topic: str = "",
    turn_count: int = 6,
    conversation_result: ConversationResult | None = None,
) -> dict[str, object]:
    """Build the shared template context for conversation pages."""
    return {
        "page_title": "Multi-Agent Fictional Personalities",
        "provider_name": "mock",
        "selected_characters": selected_characters,
        "topic_value": topic,
        "turn_count_value": turn_count,
        "conversation_result": conversation_result,
    }


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
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=_page_context(),
        )

    @application.post(
        "/conversations",
        response_class=HTMLResponse,
        name="start_conversation",
    )
    def start_conversation(
        request: Request,
        characters: Annotated[list[str], Form()],
        topic: Annotated[str, Form()],
        turn_count: Annotated[int, Form()],
    ) -> HTMLResponse:
        """Run and persist a deterministic mock conversation."""
        if not 2 <= turn_count <= 12:
            raise HTTPException(
                status_code=400,
                detail="turn_count must be between 2 and 12",
            )

        try:
            result = run_mock_conversation(
                character_slugs=characters,
                topic=topic,
                turn_count=turn_count,
                seed=42,
                output_root=OUTPUT_ROOT,
                project_root=PROJECT_ROOT,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=_page_context(
                selected_characters=characters,
                topic=topic,
                turn_count=turn_count,
                conversation_result=result,
            ),
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        """Report local application availability without external calls."""
        return {"status": "ok", "provider": "mock"}

    return application


app = create_app()
