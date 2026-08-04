"""Minimal FastAPI application for the local Sprint 4 interface."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


def create_app() -> FastAPI:
    """Create the local web application without starting a server."""
    application = FastAPI(
        title="Multi-Agent Fictional Personalities",
        description=(
            "Local mock conversation interface for fictional detective agents."
        ),
        version="0.1.0",
    )

    @application.get("/", response_class=HTMLResponse)
    def home() -> HTMLResponse:
        """Return a minimal page confirming that the web interface is ready."""
        return HTMLResponse(
            content="""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Multi-Agent Fictional Personalities</title>
</head>
<body>
    <main>
        <h1>Sprint 4 Web UI</h1>
        <p>
            The local conversation interface for Sherlock Holmes and
            Hercule Poirot is being prepared.
        </p>
        <p>Current provider: <strong>mock</strong>.</p>
    </main>
</body>
</html>
""",
            status_code=200,
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        """Report local application availability without external calls."""
        return {"status": "ok", "provider": "mock"}

    return application


app = create_app()
