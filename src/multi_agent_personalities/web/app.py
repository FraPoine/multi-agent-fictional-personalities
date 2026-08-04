"""Minimal FastAPI application for the local Sprint 4 interface."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


WEB_DIRECTORY = Path(__file__).resolve().parent
TEMPLATE_DIRECTORY = WEB_DIRECTORY / "templates"
STATIC_DIRECTORY = WEB_DIRECTORY / "static"
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORY)


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
            context={
                "page_title": "Multi-Agent Fictional Personalities",
                "provider_name": "mock",
            },
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        """Report local application availability without external calls."""
        return {"status": "ok", "provider": "mock"}

    return application


app = create_app()
