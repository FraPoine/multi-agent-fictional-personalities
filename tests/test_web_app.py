"""Integration tests for the local FastAPI web interface."""

import importlib
import json
import re
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from tests.asgi_client import ASGITestClient

from multi_agent_personalities.models import Persona


web_module = importlib.import_module("multi_agent_personalities.web.app")

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TOPIC = "A valuable document disappeared from a locked room."
EXPECTED_ARTIFACTS = (
    "run.json",
    "messages.jsonl",
    "transcript.md",
)
VALID_FORM_DATA = {
    "characters": ["sherlock", "poirot"],
    "topic": TOPIC,
    "turn_count": "6",
}


@pytest.fixture(autouse=True)
def reject_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail immediately if conversation execution attempts a network call."""

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)


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
) -> Iterator[tuple[ASGITestClient, Path]]:
    project_root = tmp_path / "synthetic_project"
    output_root = project_root / "outputs"
    create_synthetic_web_project(project_root)
    application = web_module.create_app(
        project_root=project_root,
        output_root=output_root,
    )
    with ASGITestClient(application) as client:
        yield client, output_root


def assert_html_response(response: Any, status_code: int) -> None:
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("text/html")


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
        {
            "characters": ["sherlock", "poirot"],
            "topic": "   ",
            "turn_count": "4",
        },
        "Enter an investigation topic.",
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
        "run_mock_conversation",
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
        "run_mock_conversation",
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

    monkeypatch.setattr(web_module, "run_mock_conversation", fail_service)

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
