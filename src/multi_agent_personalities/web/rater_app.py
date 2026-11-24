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

from multi_agent_personalities.evaluation.persistence import (
    load_jsonl,
    submit_rater_response,
)
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
            submit_rater_response(directory, response)
        except (ValueError, OSError, RuntimeError) as error:
            logger.warning("Rater response rejected: %s", error)
            return render(request, rater_id=rater_id, trial=trial, error=str(error), status_code=400)
        return RedirectResponse(url=f"/?rater_id={rater_id}", status_code=303)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "pilot_id": pilot_id}

    return app


def create_three_persona_rater_app(*, benchmark_directory: Path) -> FastAPI:
    """Serve an approved benchmark without loading its private answer key."""
    from fastapi import HTTPException
    from multi_agent_personalities.evaluation.benchmark_human import (
        BenchmarkResponse, Familiarity, _manifest, _records, load_public,
        rater_order, require_review, submit_familiarity, submit_response,
    )

    directory = Path(benchmark_directory)
    require_review(directory)
    manifest = _manifest(directory)
    load_public(directory)
    app = FastAPI(title='Three-persona blind identification')
    names = {**NAMES, 'professor_layton': 'Professor Layton'}

    def checked():
        try:
            require_review(directory)
            return load_public(directory)
        except (ValueError, OSError):
            raise HTTPException(status_code=503, detail='Review approval is missing or invalid')

    def display(request, rater_id='', error=None, status=200):
        trials = checked()
        familiarity = _records(directory, 'familiarity.jsonl', Familiarity)
        responses = _records(directory, 'responses.jsonl', BenchmarkResponse)
        screened = any(x.rater_id == rater_id for x in familiarity)
        answered = {x.trial_id for x in responses if x.rater_id == rater_id}
        order, choices = rater_order(trials, manifest['seed'], rater_id)
        trial = next((x for x in order if x.trial_id not in answered), None) if screened else None
        context = {'rater_id': rater_id, 'error': error, 'screened': screened, 'trial': trial,
                   'complete': screened and trial is None, 'count': len(answered), 'total': len(trials),
                   'names': names, 'candidates': [(key, names[key]) for key in choices[trial.trial_id]] if trial else []}
        return templates.TemplateResponse(request=request, name='benchmark_rater.html', context=context, status_code=status)

    @app.get('/', response_class=HTMLResponse)
    async def home(request: Request, rater_id: str = ''):
        if rater_id and not RATER_PATTERN.fullmatch(rater_id):
            return display(request, error='Use a pseudonymous ID of 3–64 letters, numbers, underscores, or hyphens.', status=400)
        return display(request, rater_id=rater_id)

    @app.post('/familiarity', response_class=HTMLResponse)
    async def familiarity(request: Request, rater_id: Annotated[str, Form()], sherlock_holmes: Annotated[str, Form()], hercule_poirot: Annotated[str, Form()], professor_layton: Annotated[str, Form()]):
        checked()
        try:
            submit_familiarity(directory, rater_id, {'sherlock_holmes': int(sherlock_holmes), 'hercule_poirot': int(hercule_poirot), 'professor_layton': int(professor_layton)})
        except (ValueError, OSError) as error:
            return display(request, rater_id=rater_id if RATER_PATTERN.fullmatch(rater_id) else '', error=str(error), status=400)
        return RedirectResponse(url=f'/?rater_id={rater_id}', status_code=303)

    @app.post('/responses', response_class=HTMLResponse)
    async def submit(request: Request, rater_id: Annotated[str, Form()], trial_id: Annotated[str, Form()], selected_character_id: Annotated[str, Form()], confidence: Annotated[str, Form()]):
        checked()
        try:
            submit_response(directory, rater_id, trial_id, selected_character_id, int(confidence))
        except (ValueError, OSError) as error:
            return display(request, rater_id=rater_id if RATER_PATTERN.fullmatch(rater_id) else '', error=str(error), status=400)
        return RedirectResponse(url=f'/?rater_id={rater_id}', status_code=303)

    return app
