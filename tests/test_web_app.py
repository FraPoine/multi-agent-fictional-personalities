"""Integration tests for the local FastAPI web interface."""

import importlib
import json
import re
import socket
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import APIRouter
from tests.asgi_client import ASGITestClient

from multi_agent_personalities.application import ConversationResult
from multi_agent_personalities.models import (
    ConversationRun,
    GenerationMetadata,
    Message,
    Persona,
)
from multi_agent_personalities.case_catalog import (
    default_case_catalog_directory,
    load_case_catalog,
)
from multi_agent_personalities.web.investigation_store import InMemoryInvestigationRegistry


web_module = importlib.import_module("multi_agent_personalities.web.app")

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_CASE_CATALOG = load_case_catalog(
    default_case_catalog_directory(REPOSITORY_ROOT)
)
TOPIC = "A valuable document disappeared from a locked room."
EXPECTED_ARTIFACTS = (
    "run.json",
    "messages.jsonl",
    "transcript.md",
)


def test_catalogue_injection_keeps_default_content_and_conclusions() -> None:
    injected_registry = InMemoryInvestigationRegistry()
    application = web_module.create_app(
        project_root=REPOSITORY_ROOT,
        case_catalog=REPOSITORY_CASE_CATALOG,
        investigation_registry=injected_registry,
    )
    assert application.state.case_content_catalog is injected_registry.case_content_catalog
    assert application.state.public_conclusion_catalog is injected_registry.public_conclusion_catalog
    assert {case.case_id for case in injected_registry.case_content_catalog.cases} == {
        case.case_id for case in injected_registry.public_conclusion_catalog.cases
    } == {
        "demo-1-vanishing-from-hyde-park",
        "demo-2-an-irregular-meeting",
        "demo-3-the-disappearance-of-a-student",
    }
VALID_FORM_DATA = {
    "characters": ["sherlock", "poirot"],
    "topic": TOPIC,
    "turn_count": "6",
}


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail immediately if conversation execution attempts a network call."""

    original_connect = socket.socket.connect

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    def reject_internet_connect(
        connection: socket.socket,
        address: object,
    ) -> None:
        if connection.family in (socket.AF_INET, socket.AF_INET6):
            raise AssertionError("network access attempted")
        original_connect(connection, address)  # type: ignore[arg-type]

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", reject_internet_connect)

    async def run_inline(function, *args, **kwargs):
        """Keep ordinary route tests compatible with the sandbox's socket ban."""
        return function(*args, **kwargs)

    monkeypatch.setattr(web_module.asyncio, "to_thread", run_inline)


@pytest.fixture
def web_client(
    tmp_path: Path,
) -> Iterator[tuple[ASGITestClient, Path]]:
    """Provide a client whose real mock runs persist only beneath tmp_path."""
    output_root = tmp_path / "outputs"
    application = web_module.create_app(
        project_root=REPOSITORY_ROOT,
        output_root=output_root,
    )
    with ASGITestClient(application) as client:
        yield client, output_root


def create_synthetic_web_project(project_root: Path) -> None:
    """Create three catalog characters and mock assets under a temporary root."""

    config_directory = project_root / "configs"
    assets_directory = project_root / "assets"
    config_directory.mkdir(parents=True)
    characters = (
        ("alpha", "agent-alpha", "Agent Alpha"),
        ("beta", "agent-beta", "Beta"),
        ("gamma", "agent-gamma", "Agent Gamma"),
    )
    entries: list[dict[str, str]] = []
    for slug, character_id, display_name in characters:
        character_directory = assets_directory / slug
        character_directory.mkdir(parents=True)
        (character_directory / "corpus.jsonl").write_text(
            '{"text":"Synthetic web evidence."}\n',
            encoding="utf-8",
        )
        persona = Persona(
            character_id=character_id,
            display_name=display_name,
            description="Synthetic web-test persona.",
            speaking_style=["Neutral"],
            reasoning_style=["Deterministic"],
            personality_traits=["Test-only"],
            behavior_rules=["Use test data"],
            example_messages=[f"response-from-{slug}"],
        )
        (character_directory / "persona.json").write_text(
            persona.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        (character_directory / "response.txt").write_text(
            f"response-from-{slug}\n",
            encoding="utf-8",
        )
        entries.append(
            {
                "slug": slug,
                "character_id": character_id,
                "display_name": display_name,
                "description": f"Synthetic description for {display_name}.",
                "corpus_path": f"../assets/{slug}/corpus.jsonl",
                "persona_fixture_path": f"../assets/{slug}/persona.json",
                "mock_response_fixture_path": f"../assets/{slug}/response.txt",
            }
        )
    (config_directory / "characters.yaml").write_text(
        yaml.safe_dump({"characters": entries}, sort_keys=False),
        encoding="utf-8",
    )


@pytest.fixture
def synthetic_web_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[ASGITestClient, Path]]:
    project_root = tmp_path / "synthetic_project"
    output_root = project_root / "outputs"
    create_synthetic_web_project(project_root)

    investigation_router = APIRouter()

    @investigation_router.get(
        "/investigations",
        name="investigations_index",
    )
    async def synthetic_investigations_index() -> dict[str, str]:
        return {"detail": "not part of the synthetic conversation fixture"}

    monkeypatch.setattr(
        web_module,
        "create_investigation_router",
        lambda **_: investigation_router,
    )
    application = web_module.create_app(
        project_root=project_root,
        output_root=output_root,
        case_catalog=REPOSITORY_CASE_CATALOG,
    )
    with ASGITestClient(application) as client:
        yield client, output_root


def assert_html_response(response: Any, status_code: int) -> None:
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("text/html")


def test_create_app_shares_one_loaded_case_catalog_with_registry_and_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    load_calls: list[Path] = []
    captured: dict[str, object] = {}

    def load_once(path: Path):
        load_calls.append(path)
        return REPOSITORY_CASE_CATALOG

    def capture_router(**kwargs: object) -> APIRouter:
        captured.update(kwargs)
        return APIRouter()

    monkeypatch.setattr(web_module, "load_case_catalog", load_once)
    monkeypatch.setattr(web_module, "create_investigation_router", capture_router)

    application = web_module.create_app(project_root=REPOSITORY_ROOT)

    assert len(load_calls) == 1
    assert application.state.case_catalog is REPOSITORY_CASE_CATALOG
    assert (
        application.state.investigation_registry.case_catalog
        is REPOSITORY_CASE_CATALOG
    )
    assert captured["case_catalog"] is REPOSITORY_CASE_CATALOG


def assert_no_completed_run(output_root: Path) -> None:
    runs_directory = output_root / "conversations" / "runs"
    assert not runs_directory.exists() or list(runs_directory.iterdir()) == []


def extract_run_id(document: str) -> str:
    match = re.search(
        r"<dt>Run ID</dt>\s*<dd><code>([^<]+)</code></dd>",
        document,
    )
    assert match is not None
    return match.group(1)


def post_valid_conversation(client: ASGITestClient) -> Any:
    return client.post("/conversations", data=VALID_FORM_DATA)


def fake_conversation_result(
    output_root: Path,
    *,
    provider: str,
    model: str | None,
) -> ConversationResult:
    created_at = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
    messages = tuple(
        Message(
            message_id=f"web_fake_message_{turn_index}",
            run_id="web_fake_run",
            turn_index=turn_index,
            speaker_character_id=character_id,
            speaker_name=display_name,
            text=f"Offline response {turn_index + 1}.",
            provider=provider,
            model=model,
            generation_metadata=GenerationMetadata(
                provider=provider,
                model=model,
            ),
            timestamp=created_at,
        )
        for turn_index, (character_id, display_name) in enumerate(
            (
                ("sherlock_holmes", "Sherlock Holmes"),
                ("hercule_poirot", "Hercule Poirot"),
            )
        )
    )
    run = ConversationRun(
        run_id="web_fake_run",
        topic=TOPIC,
        character_ids=("sherlock_holmes", "hercule_poirot"),
        turn_count=2,
        seed=42,
        provider=provider,
        model=model,
        created_at=created_at,
        status="completed",
        messages=messages,
    )
    return ConversationResult(
        run=run,
        artifact_directory=(
            output_root / "conversations" / "runs" / run.run_id
        ),
    )


def assert_failed_without_result(response: Any, status_code: int) -> None:
    assert_html_response(response, status_code)
    assert "status-label--failed" in response.text
    assert ">Failed</span>" in response.text
    assert "status-label--completed" not in response.text
    assert 'class="message-card' not in response.text
    assert 'class="run-details"' not in response.text
    assert "outputs/conversations/runs/" not in response.text


def test_main_page_renders_without_creating_output(
    web_client: tuple[ASGITestClient, Path],
) -> None:
    client, output_root = web_client

    response = client.get("/")

    assert_html_response(response, 200)
    assert "Multi-Agent Fictional Personalities" in response.text
    assert "New investigation" in response.text
    assert "Sherlock Holmes" in response.text
    assert "Hercule Poirot" in response.text
    assert "mock provider" in response.text
    assert 'aria-current="page">Conversations</a>' in response.text
    assert '>Investigations</a>' in response.text
    assert 'aria-current="page">Investigations</a>' not in response.text
    assert 'method="post"' in response.text
    assert 'action="http://testserver/conversations"' in response.text
    for loading_hook in (
        "data-conversation-form",
        "data-submit-button",
        "data-submit-label",
        "data-transcript-panel",
        "data-transcript-status",
        "data-transcript-body",
    ):
        assert loading_hook in response.text
    assert "Awaiting case" in response.text
    assert "status-label--completed" not in response.text
    assert 'class="message-card' not in response.text
    assert "Run ID" not in response.text
    assert "outputs/conversations/runs/" not in response.text
    assert_no_completed_run(output_root)


def test_mock_provider_is_selected_by_default(
    web_client: tuple[ASGITestClient, Path],
) -> None:
    client, _ = web_client
    response = client.get("/")

    provider_select = re.search(
        r'<select[^>]*id="provider"[^>]*>(.*?)</select>',
        response.text,
        re.DOTALL,
    )
    assert provider_select is not None
    assert re.search(
        r'<option value="mock" selected>Mock</option>',
        provider_select.group(1),
    )
    assert '<option value="copilot">Copilot</option>' in provider_select.group(1)
    assert 'name="copilot_model"' in response.text
    assert 'value=""' in response.text


def test_default_catalog_controls_are_accessible_and_selected(
    web_client: tuple[ASGITestClient, Path],
) -> None:
    client, _ = web_client

    response = client.get("/")
    controls = re.findall(
        r'<input\s+[^>]*id="(character-[^"]+)"[^>]*name="characters"'
        r'[^>]*value="([^"]+)"[^>]*>',
        response.text,
    )

    assert controls == [
        ("character-sherlock", "sherlock"),
        ("character-poirot", "poirot"),
    ]
    assert len({control_id for control_id, _ in controls}) == len(controls)
    for control_id, _ in controls:
        input_tag = re.search(
            rf'<input\s+[^>]*id="{control_id}"[^>]*>',
            response.text,
        )
        assert input_tag is not None and "checked" in input_tag.group()
        assert f'for="{control_id}"' in response.text
    assert ">SH</span>" in response.text
    assert ">HP</span>" in response.text
    assert "participant-tone-1" in response.text
    assert "participant-tone-2" in response.text


def test_three_character_catalog_renders_in_order_with_generic_metadata(
    synthetic_web_client: tuple[ASGITestClient, Path],
) -> None:
    client, output_root = synthetic_web_client

    response = client.get("/")

    assert_html_response(response, 200)
    assert response.text.index("Agent Alpha") < response.text.index("Beta")
    assert response.text.index("Beta") < response.text.index("Agent Gamma")
    for slug, initials, tone in (
        ("alpha", "AA", 1),
        ("beta", "B", 2),
        ("gamma", "AG", 3),
    ):
        input_tag = re.search(
            rf'<input\s+[^>]*id="character-{slug}"[^>]*>',
            response.text,
        )
        assert input_tag is not None and "checked" in input_tag.group()
        assert f'for="character-{slug}"' in response.text
        assert f'value="{slug}"' in input_tag.group()
        assert f">{initials}</span>" in response.text
        assert f"participant-tone-{tone}" in response.text
    assert "Sherlock" not in response.text
    assert "Poirot" not in response.text
    assert_no_completed_run(output_root)


def test_two_of_three_selection_uses_catalog_form_order(
    synthetic_web_client: tuple[ASGITestClient, Path],
) -> None:
    client, _ = synthetic_web_client

    response = client.post(
        "/conversations",
        data={
            "characters": ["alpha", "gamma"],
            "topic": TOPIC,
            "turn_count": "4",
        },
    )

    assert_html_response(response, 200)
    transcript = response.text.split(
        '<ol class="transcript-list"',
        maxsplit=1,
    )[1].split("</ol>", maxsplit=1)[0]
    markers = [
        "response-from-alpha",
        "response-from-gamma",
        "response-from-alpha",
        "response-from-gamma",
    ]
    cursor = 0
    for marker in markers:
        cursor = transcript.index(marker, cursor) + len(marker)
    assert "response-from-beta" not in transcript
    beta_input = re.search(
        r'<input\s+[^>]*id="character-beta"[^>]*>',
        response.text,
    )
    assert beta_input is not None and "checked" not in beta_input.group()


def test_three_participant_submission_preserves_message_order(
    synthetic_web_client: tuple[ASGITestClient, Path],
) -> None:
    client, _ = synthetic_web_client

    response = client.post(
        "/conversations",
        data={
            "characters": ["alpha", "beta", "gamma"],
            "topic": TOPIC,
            "turn_count": "5",
        },
    )

    assert_html_response(response, 200)
    transcript = response.text.split(
        '<ol class="transcript-list"',
        maxsplit=1,
    )[1].split("</ol>", maxsplit=1)[0]
    expected = [
        "response-from-alpha",
        "response-from-beta",
        "response-from-gamma",
        "response-from-alpha",
        "response-from-beta",
    ]
    cursor = 0
    for marker in expected:
        cursor = transcript.index(marker, cursor) + len(marker)
    assert transcript.count('class="message-card') == 5


@pytest.mark.parametrize(
    ("characters", "error"),
    [
        ([], "Select at least two characters."),
        (["alpha"], "Select at least two characters."),
        (
            ["alpha", "beta", "alpha"],
            "Select each available character only once.",
        ),
        (
            ["alpha", "beta", "unknown"],
            "Select only currently available characters.",
        ),
    ],
)
def test_synthetic_invalid_participants_fail_before_persistence(
    synthetic_web_client: tuple[ASGITestClient, Path],
    characters: list[str],
    error: str,
) -> None:
    client, output_root = synthetic_web_client

    response = client.post(
        "/conversations",
        data={"characters": characters, "topic": TOPIC, "turn_count": "5"},
    )

    assert_failed_without_result(response, 400)
    assert error in response.text
    assert_no_completed_run(output_root)


def test_health_route_is_side_effect_free(
    web_client: tuple[ASGITestClient, Path],
) -> None:
    client, output_root = web_client

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "provider": "mock"}
    assert_no_completed_run(output_root)


def test_static_assets_are_served(
    web_client: tuple[ASGITestClient, Path],
) -> None:
    client, _ = web_client

    stylesheet = client.get("/static/styles.css")
    script = client.get("/static/conversation.js")

    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert "data-conversation-form" in script.text


def test_valid_submission_renders_completed_conversation(
    web_client: tuple[ASGITestClient, Path],
) -> None:
    client, output_root = web_client

    response = post_valid_conversation(client)

    assert_html_response(response, 200)
    assert "status-label--completed" in response.text
    assert ">Completed</span>" in response.text
    assert "status-label--failed" not in response.text
    assert "Sherlock Holmes" in response.text
    assert "Hercule Poirot" in response.text
    assert response.text.count('class="message-card') == 6

    transcript = response.text.split(
        '<ol class="transcript-list"',
        maxsplit=1,
    )[1].split("</ol>", maxsplit=1)[0]
    for turn_number in range(1, 7):
        assert f"Turn {turn_number}" in transcript
    assert transcript.index("Sherlock Holmes") < transcript.index(
        "Hercule Poirot"
    )

    assert 'class="run-details"' in response.text
    run_id = extract_run_id(response.text)
    assert run_id
    assert response.text.count('class="artifact-item"') == 3
    for filename in EXPECTED_ARTIFACTS:
        assert filename in response.text
    assert f"outputs/conversations/runs/{run_id}" in response.text
    assert str(REPOSITORY_ROOT) not in response.text
    assert str(output_root.parent) not in response.text


def test_valid_submission_creates_and_displays_artifacts(
    web_client: tuple[ASGITestClient, Path],
) -> None:
    client, output_root = web_client

    response = post_valid_conversation(client)
    run_id = extract_run_id(response.text)
    runs_directory = output_root / "conversations" / "runs"
    run_directories = list(runs_directory.iterdir())

    assert len(run_directories) == 1
    run_directory = run_directories[0]
    assert run_directory.name == run_id
    assert tuple(sorted(path.name for path in run_directory.iterdir())) == tuple(
        sorted(EXPECTED_ARTIFACTS)
    )

    run_data = json.loads(
        (run_directory / "run.json").read_text(encoding="utf-8")
    )
    assert run_data["status"] == "completed"
    assert run_data["topic"] == TOPIC
    assert run_data["turn_count"] == 6
    assert run_data["provider"] == "mock"
    assert len(run_data["messages"]) == 6

    message_lines = [
        line
        for line in (run_directory / "messages.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    assert len(message_lines) == 6
    transcript = (run_directory / "transcript.md").read_text(encoding="utf-8")
    assert "Sherlock Holmes" in transcript
    assert "Hercule Poirot" in transcript


@pytest.mark.parametrize(
    ("submitted_model", "expected_model"),
    (("", None), ("  gpt-test  ", "gpt-test")),
)
def test_copilot_selection_reaches_service_with_normalized_arguments(
    web_client: tuple[ASGITestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
    submitted_model: str,
    expected_model: str | None,
) -> None:
    client, output_root = web_client
    captured: dict[str, object] = {}

    def fake_service(**kwargs: object) -> ConversationResult:
        captured.update(kwargs)
        return fake_conversation_result(
            output_root,
            provider="copilot",
            model=expected_model or "sdk-default-model",
        )

    monkeypatch.setattr(web_module, "run_conversation", fake_service)
    response = client.post(
        "/conversations",
        data={
            **VALID_FORM_DATA,
            "turn_count": "2",
            "provider": "copilot",
            "copilot_model": submitted_model,
        },
    )

    assert_html_response(response, 200)
    assert captured == {
        "character_slugs": ["sherlock", "poirot"],
        "topic": TOPIC,
        "turn_count": 2,
        "provider": "copilot",
        "copilot_model": expected_model,
        "seed": 42,
        "output_root": output_root,
        "project_root": REPOSITORY_ROOT,
    }
    assert "copilot provider" in response.text
    assert 'value="copilot" selected' in response.text
    assert f'value="{submitted_model}"' in response.text
    assert 'class="message-card' in response.text
    assert 'class="run-details"' in response.text


def test_conversation_generation_is_delegated_to_threadpool(
    web_client: tuple[ASGITestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, output_root = web_client
    offloaded: list[object] = []

    async def capture_offload(function, *args, **kwargs):
        offloaded.append(function)
        return function(*args, **kwargs)

    monkeypatch.setattr(web_module.asyncio, "to_thread", capture_offload)
    monkeypatch.setattr(
        web_module,
        "run_conversation",
        lambda **_: fake_conversation_result(
            output_root, provider="mock", model="mock-round-robin"
        ),
    )

    response = post_valid_conversation(client)

    assert response.status_code == 200
    assert len(offloaded) == 1
    assert callable(offloaded[0])


@pytest.mark.parametrize(
    ("form_data", "field_error"),
    (
        (
            {**VALID_FORM_DATA, "provider": "unknown"},
            "Select Mock or Copilot.",
        ),
        (
            {
                **VALID_FORM_DATA,
                "provider": "copilot",
                "copilot_model": "x" * 101,
            },
            "Enter a model identifier of at most 100 printable characters.",
        ),
        (
            {
                **VALID_FORM_DATA,
                "provider": "mock",
                "copilot_model": "gpt-test",
            },
            "A Copilot model can only be set when Copilot is selected.",
        ),
    ),
)
def test_invalid_provider_configuration_is_rejected_before_service(
    web_client: tuple[ASGITestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
    form_data: dict[str, object],
    field_error: str,
) -> None:
    client, output_root = web_client
    monkeypatch.setattr(
        web_module,
        "run_conversation",
        lambda **_: pytest.fail("service called for invalid provider form"),
    )

    response = client.post("/conversations", data=form_data)

    assert_failed_without_result(response, 400)
    assert field_error in response.text
    assert_no_completed_run(output_root)


def test_copilot_values_survive_unrelated_validation_error(
    web_client: tuple[ASGITestClient, Path],
) -> None:
    client, _ = web_client
    response = client.post(
        "/conversations",
        data={
            "characters": ["sherlock"],
            "topic": TOPIC,
            "turn_count": "2",
            "provider": "copilot",
            "copilot_model": "gpt-test",
        },
    )

    assert_failed_without_result(response, 400)
    assert 'value="copilot" selected' in response.text
    assert 'value="gpt-test"' in response.text
    assert "copilot provider" in response.text


@pytest.mark.parametrize(
    ("error", "status_code", "safe_message"),
    (
        (
            RuntimeError("token secret from /private/sdk/auth"),
            502,
            "Confirm that GitHub CLI authentication and Copilot access",
        ),
        (
            TimeoutError("request timed out at /private/sdk/session"),
            504,
            "Copilot did not finish in time.",
        ),
        (
            ValueError("reported model mismatch: private-model"),
            500,
            "could not be generated with the selected model",
        ),
    ),
)
def test_copilot_failures_render_safe_provider_specific_errors(
    web_client: tuple[ASGITestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
    safe_message: str,
) -> None:
    client, output_root = web_client

    def fail_service(**kwargs: object) -> None:
        raise error

    monkeypatch.setattr(web_module, "run_conversation", fail_service)
    response = client.post(
        "/conversations",
        data={
            **VALID_FORM_DATA,
            "provider": "copilot",
            "copilot_model": "gpt-test",
        },
    )

    assert_failed_without_result(response, status_code)
    assert safe_message in response.text
    assert str(error) not in response.text
    assert "/private/" not in response.text
    assert "copilot provider" in response.text
    assert 'value="copilot" selected' in response.text
    assert 'value="gpt-test"' in response.text
    assert_no_completed_run(output_root)


def test_read_only_routes_create_no_conversation_output(
    web_client: tuple[ASGITestClient, Path],
) -> None:
    client, output_root = web_client

    for path in (
        "/",
        "/health",
        "/static/styles.css",
        "/static/conversation.js",
    ):
        assert client.get(path).status_code == 200

    assert_no_completed_run(output_root)


INVALID_SUBMISSIONS = (
    (
        {"topic": TOPIC, "turn_count": "4"},
        "Select at least two characters.",
    ),
    (
        {"characters": ["sherlock"], "topic": TOPIC, "turn_count": "4"},
        "Select at least two characters.",
    ),
    (
        {
            "characters": ["sherlock", "sherlock"],
            "topic": TOPIC,
            "turn_count": "4",
        },
        "Select each available character only once.",
    ),
    (
        {
            "characters": ["sherlock", "unknown"],
            "topic": TOPIC,
            "turn_count": "4",
        },
        "Select only currently available characters.",
    ),
    (
        {"characters": ["sherlock", "poirot"], "topic": TOPIC},
        "Enter a whole number between 2 and 12.",
    ),
    (
        {
            "characters": ["sherlock", "poirot"],
            "topic": TOPIC,
            "turn_count": "abc",
        },
        "Enter a whole number between 2 and 12.",
    ),
    (
        {
            "characters": ["sherlock", "poirot"],
            "topic": TOPIC,
            "turn_count": "4.5",
        },
        "Enter a whole number between 2 and 12.",
    ),
    (
        {
            "characters": ["sherlock", "poirot"],
            "topic": TOPIC,
            "turn_count": "1",
        },
        "Enter a whole number between 2 and 12.",
    ),
    (
        {
            "characters": ["sherlock", "poirot"],
            "topic": TOPIC,
            "turn_count": "13",
        },
        "Enter a whole number between 2 and 12.",
    ),
)


@pytest.mark.parametrize(("form_data", "field_error"), INVALID_SUBMISSIONS)
def test_invalid_submissions_render_field_errors_without_calling_service(
    web_client: tuple[ASGITestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
    form_data: dict[str, object],
    field_error: str,
) -> None:
    client, output_root = web_client

    def unexpected_service_call(**kwargs: object) -> None:
        raise AssertionError("service called for invalid form")

    monkeypatch.setattr(
        web_module,
        "run_conversation",
        unexpected_service_call,
    )

    response = client.post("/conversations", data=form_data)

    assert_failed_without_result(response, 400)
    assert "Please correct the highlighted fields and submit again." in (
        response.text
    )
    assert field_error in response.text
    assert_no_completed_run(output_root)


def test_invalid_submission_preserves_safe_values(
    web_client: tuple[ASGITestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, output_root = web_client

    def unexpected_service_call(**kwargs: object) -> None:
        raise AssertionError("service called for invalid form")

    monkeypatch.setattr(
        web_module,
        "run_conversation",
        unexpected_service_call,
    )
    response = client.post(
        "/conversations",
        data={
            "characters": ["sherlock"],
            "topic": "A preserved topic",
            "turn_count": "abc",
        },
    )

    assert_failed_without_result(response, 400)
    sherlock_input = re.search(
        r'<input\s+[^>]*id="character-sherlock"[^>]*>',
        response.text,
    )
    poirot_input = re.search(
        r'<input\s+[^>]*id="character-poirot"[^>]*>',
        response.text,
    )
    assert sherlock_input is not None and "checked" in sherlock_input.group()
    assert poirot_input is not None and "checked" not in poirot_input.group()
    assert ">A preserved topic</textarea>" in response.text
    assert 'value="abc"' in response.text
    assert "Select at least two characters." in response.text
    assert "Enter a whole number between 2 and 12." in response.text
    assert_no_completed_run(output_root)


@pytest.mark.parametrize(
    ("error", "status_code", "safe_message"),
    (
        (
            ValueError("invalid fixture at /private/example/persona.json"),
            500,
            "The local mock conversation could not be generated.",
        ),
        (
            FileExistsError(
                "conversation run already exists: /private/example/run"
            ),
            409,
            "A run with the generated identifier already exists.",
        ),
        (
            OSError("permission denied: /private/example/outputs"),
            500,
            "The conversation could not be saved.",
        ),
    ),
)
def test_service_errors_render_safe_failed_state(
    web_client: tuple[ASGITestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
    error: OSError | ValueError,
    status_code: int,
    safe_message: str,
) -> None:
    client, output_root = web_client

    def fail_service(**kwargs: object) -> None:
        raise error

    monkeypatch.setattr(web_module, "run_conversation", fail_service)

    response = post_valid_conversation(client)

    assert_failed_without_result(response, status_code)
    assert safe_message in response.text
    assert str(error) not in response.text
    assert "/private/example/" not in response.text
    assert_no_completed_run(output_root)


def test_topic_is_html_escaped(
    web_client: tuple[ASGITestClient, Path],
) -> None:
    client, _ = web_client
    topic = '<script>alert("case")</script>'

    response = client.post(
        "/conversations",
        data={
            "characters": ["sherlock", "poirot"],
            "topic": topic,
            "turn_count": "2",
        },
    )

    assert_html_response(response, 200)
    assert "status-label--completed" in response.text
    assert '<script>alert("case")</script>' not in response.text
    assert "&lt;script&gt;alert" in response.text
    assert "&lt;/script&gt;" in response.text
    assert response.text.count("<script") == 1
    assert "/static/conversation.js" in response.text


def test_initial_topic_is_editable_default(
    web_client: tuple[ASGITestClient, Path],
) -> None:
    client, _ = web_client
    response = client.get("/")
    textarea = re.search(r'<textarea\b[^>]*name="topic"[^>]*>(.*?)</textarea>', response.text, re.S)
    assert textarea is not None
    assert textarea.group(1) == web_module.DEFAULT_CONVERSATION_TOPIC
    assert "required" not in textarea.group(0)


@pytest.mark.parametrize("provider", ("mock", "copilot"))
@pytest.mark.parametrize("topic", (None, "", " \t\n ", "A custom mystery", "  A custom mystery  "))
def test_topic_resolution_reaches_generated_run(
    web_client: tuple[ASGITestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    topic: str | None,
) -> None:
    client, output_root = web_client
    real_service = web_module.run_conversation
    generated_runs: list[ConversationRun] = []

    def offline_service(**kwargs: Any) -> ConversationResult:
        assert kwargs["provider"] == provider
        # Exercise real generation and persistence offline for either form selection.
        kwargs["provider"] = "mock"
        result = real_service(**kwargs)
        generated_runs.append(result.run)
        return result

    monkeypatch.setattr(web_module, "run_conversation", offline_service)
    data = {**VALID_FORM_DATA, "provider": provider, "turn_count": "2"}
    if topic is None:
        data.pop("topic")
    else:
        data["topic"] = topic
    response = client.post("/conversations", data=data)

    assert_html_response(response, 200)
    expected = (topic or "").strip() or web_module.DEFAULT_CONVERSATION_TOPIC
    assert len(generated_runs) == 1
    assert generated_runs[0].topic == expected
    run_path = output_root / "conversations" / "runs" / extract_run_id(response.text) / "run.json"
    assert json.loads(run_path.read_text(encoding="utf-8"))["topic"] == expected
