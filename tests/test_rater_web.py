"""Separate rater interface integration tests."""

from pathlib import Path
import asyncio
import httpx

from multi_agent_personalities.application.evaluation_service import prepare_technical_pilot
from multi_agent_personalities.web.rater_app import create_rater_app


ROOT = Path(__file__).resolve().parents[1]


def make_app(tmp_path: Path) -> tuple[object, Path]:
    result = prepare_technical_pilot(output_root=tmp_path, project_root=ROOT, config_path=ROOT / "configs/evaluation_pilot.yaml", pilot_id="pilot_web")
    return create_rater_app(pilot_directory=result.pilot_directory, pilot_id=result.pilot_id), result.pilot_directory


async def request(app: object, method: str, url: str, **kwargs: object) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        return await client.request(method, url, **kwargs)


def test_rater_page_hides_answer_and_accepts_response(tmp_path: Path) -> None:
    app, directory = make_app(tmp_path)
    page = asyncio.run(request(app, "GET", "/?rater_id=rater_001"))
    assert page.status_code == 200
    answer = (directory / "answer_key.jsonl").read_text()
    assert "correct_character_id" not in page.text
    assert answer not in page.text
    trial_id = page.text.split('name="trial_id" value="', 1)[1].split('"', 1)[0]
    response = asyncio.run(request(app, "POST", "/responses", data={"rater_id": "rater_001", "trial_id": trial_id, "selected_character_id": "sherlock_holmes", "confidence": "4"}, follow_redirects=False))
    assert response.status_code == 303
    assert len((directory / "responses.jsonl").read_text().splitlines()) == 1


def test_invalid_submission_is_readable_and_not_persisted(tmp_path: Path) -> None:
    app, directory = make_app(tmp_path)
    page = asyncio.run(request(app, "GET", "/?rater_id=rater_001"))
    trial_id = page.text.split('name="trial_id" value="', 1)[1].split('"', 1)[0]
    response = asyncio.run(request(app, "POST", "/responses", data={"rater_id": "rater_001", "trial_id": trial_id, "selected_character_id": "sherlock_holmes", "confidence": "9"}))
    assert response.status_code == 400
    assert 'role="alert"' in response.text
    assert (directory / "responses.jsonl").read_text() == ""
