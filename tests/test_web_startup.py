"""Tests for the local FastAPI startup command."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SCRIPT = PROJECT_ROOT / "scripts" / "run_web.py"


def load_startup_module() -> ModuleType:
    """Load the standalone script without making scripts a package."""
    specification = importlib.util.spec_from_file_location(
        "run_web_for_tests",
        STARTUP_SCRIPT,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def startup_module() -> ModuleType:
    return load_startup_module()


def capture_uvicorn_run(
    startup_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[tuple[object, ...], dict[str, object]]]:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def record(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(startup_module.uvicorn, "run", record)
    return calls


def test_default_invocation_runs_existing_application_once(
    startup_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = capture_uvicorn_run(startup_module, monkeypatch)

    assert startup_module.main([]) == 0

    assert calls == [
        (
            ("multi_agent_personalities.web.app:app",),
            {
                "app_dir": str(PROJECT_ROOT / "src"),
                "host": "127.0.0.1",
                "port": 8000,
                "reload": False,
            },
        )
    ]


def test_custom_host_and_port_are_forwarded(
    startup_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = capture_uvicorn_run(startup_module, monkeypatch)

    assert startup_module.main(
        ["--host", "0.0.0.0", "--port", "8080"]
    ) == 0

    assert len(calls) == 1
    assert calls[0][1]["host"] == "0.0.0.0"
    assert calls[0][1]["port"] == 8080


def test_reload_is_forwarded(
    startup_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = capture_uvicorn_run(startup_module, monkeypatch)

    assert startup_module.main(["--reload"]) == 0

    assert len(calls) == 1
    assert calls[0][1]["reload"] is True


@pytest.mark.parametrize("port", ("0", "65536", "abc"))
def test_invalid_ports_are_rejected_before_uvicorn_starts(
    startup_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    port: str,
) -> None:
    calls = capture_uvicorn_run(startup_module, monkeypatch)

    with pytest.raises(SystemExit) as raised:
        startup_module.main(["--port", port])

    assert raised.value.code != 0
    assert calls == []


def test_source_directory_is_independent_of_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    startup_module = load_startup_module()
    calls = capture_uvicorn_run(startup_module, monkeypatch)

    assert startup_module.main([]) == 0

    assert startup_module.PROJECT_ROOT == PROJECT_ROOT
    assert startup_module.SOURCE_DIRECTORY == PROJECT_ROOT / "src"
    assert calls[0][1]["app_dir"] == str(PROJECT_ROOT / "src")
