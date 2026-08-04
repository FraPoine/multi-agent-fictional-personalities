"""Separate local server-rendered interface for blind pilot rating."""

from datetime import datetime, timezone
import hashlib
import logging
from pathlib import Path
import re
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from multi_agent_personalities.evaluation.persistence import append_response, load_jsonl, refresh_analysis
from multi_agent_personalities.models import PublicEvaluationTrial, RaterResponse
from multi_agent_personalities.models.identifiers import validate_run_id


WEB_DIRECTORY = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=WEB_DIRECTORY / "templates")
logger = logging.getLogger(__name__)
NAMES = {"sherlock_holmes": "Sherlock Holmes", "hercule_poirot": "Hercule Poirot"}
RATER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")


def _response_id(pilot_id: str, rater_id: str, trial_id: str) -> str:
    value = hashlib.sha256(f"{pilot_id}\x1f{rater_id}\x1f{trial_id}".encode()).hexdigest()[:20]
    return f"response_{value}"


def create_rater_app(*, pilot_directory: Path, pilot_id: str) -> FastAPI:
    """Create an app bound to one already-prepared pilot."""
    validate_run_id(pilot_id)
    directory = Path(pilot_directory)
    trials = load_jsonl(directory / "trials_public.jsonl", PublicEvaluationTrial)
    if not trials:
        raise ValueError("pilot contains no trials")
    app = FastAPI(title="Blind Evaluation Rater", version="0.1.0")

    def render(request: Request, *, rater_id: str = "", trial: PublicEvaluationTrial | None = None, error: str | None = None, complete: bool = False, status_code: int = 200) -> HTMLResponse:
        candidates = [(value, NAMES[value]) for value in trial.candidate_character_ids] if trial else []
        return templates.TemplateResponse(request=request, name="rater.html", context={"pilot_id": pilot_id, "rater_id": rater_id, "trial": trial, "candidates": candidates, "error": error, "complete": complete}, status_code=status_code)

    def next_trial(rater_id: str) -> PublicEvaluationTrial | None:
        responses = load_jsonl(directory / "responses.jsonl", RaterResponse)
        answered = {item.trial_id for item in responses if item.rater_id == rater_id}
        return next((item for item in trials if item.trial_id not in answered), None)

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request, rater_id: str = "") -> HTMLResponse:
        if not rater_id:
            return render(request)
        if not RATER_PATTERN.fullmatch(rater_id):
            return render(request, rater_id=rater_id, error="Use 3–64 letters, numbers, underscores, or hyphens.", status_code=400)
        trial = next_trial(rater_id)
        return render(request, rater_id=rater_id, trial=trial, complete=trial is None)

    @app.post("/responses", response_class=HTMLResponse)
    async def submit(
        request: Request,
        rater_id: Annotated[str, Form()], trial_id: Annotated[str, Form()],
        selected_character_id: Annotated[str, Form()], confidence: Annotated[str, Form()],
        response_duration_seconds: Annotated[str | None, Form()] = None,
    ) -> HTMLResponse:
        trial = next((item for item in trials if item.trial_id == trial_id), None)
        if not RATER_PATTERN.fullmatch(rater_id) or trial is None:
            return render(request, rater_id=rater_id, trial=trial, error="Invalid rater or trial.", status_code=400)
        try:
            parsed_confidence = int(confidence)
            duration = float(response_duration_seconds) if response_duration_seconds else None
            response = RaterResponse(
                response_id=_response_id(pilot_id, rater_id, trial_id), trial_id=trial_id,
                rater_id=rater_id, selected_character_id=selected_character_id,
                confidence=parsed_confidence, timestamp=datetime.now(timezone.utc),
                response_duration_seconds=duration,
            )
            append_response(directory, response)
            refresh_analysis(directory)
        except (ValueError, OSError, RuntimeError) as error:
            logger.warning("Rater response rejected: %s", error)
            return render(request, rater_id=rater_id, trial=trial, error=str(error), status_code=400)
        return RedirectResponse(url=f"/?rater_id={rater_id}", status_code=303)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "pilot_id": pilot_id}

    return app
