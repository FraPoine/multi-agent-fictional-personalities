"""Offline adapter tests: no SDK client is ever started."""

import asyncio
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError
from copilot import CopilotClient
from copilot.session import CopilotSession
from copilot.session_events import AssistantUsageData, SessionEventType

from multi_agent_personalities.llm import copilot_provider
from multi_agent_personalities.llm.copilot_provider import CopilotProvider


@pytest.fixture
def sdk(monkeypatch):
    clients = []
    sessions = []
    options = []
    events = []

    def factory(**kwargs):
        client = create_autospec(CopilotClient, instance=True)
        session = create_autospec(CopilotSession, instance=True)
        session.send_and_wait.return_value = SimpleNamespace(
            data=SimpleNamespace(content="  A deduction.\n"),
        )

        async def create(**config):
            options.append(config)
            for data, agent_id in events:
                config["on_event"](SimpleNamespace(
                    type=SessionEventType.ASSISTANT_USAGE, data=data, agent_id=agent_id,
                ))
            return session

        client.create_session.side_effect = create
        clients.append((client, kwargs))
        sessions.append(session)
        return client

    monkeypatch.setattr(copilot_provider, "CopilotClient", factory)
    return SimpleNamespace(clients=clients, sessions=sessions, options=options, events=events)


def test_success_defaults_and_disabled_capabilities(sdk):
    provider = CopilotProvider()
    assert sdk.clients == []
    result = provider.generate("Prompt", task_name="agent_reply")
    assert result.text == "  A deduction.\n"
    assert result.metadata.model_dump() == {
        "provider": "copilot", "model": None, "usage": None,
        "finish_reason": None, "request_id": None, "latency_ms": None,
        "retry_count": 0,
    }
    config = sdk.options[0]
    assert "model" not in config
    assert config["available_tools"] == []
    assert config["mcp_servers"] == {}
    assert config["custom_agents"] == []
    assert config["enable_config_discovery"] is False
    assert config["infinite_sessions"] == {"enabled": False}
    assert config["streaming"] is False
    assert config["on_permission_request"](None, None).kind == "reject"
    client, kwargs = sdk.clients[0]
    assert kwargs["mode"] == "empty"
    assert kwargs["use_logged_in_user"] is True
    assert not Path(kwargs["base_directory"]).exists()
    sdk.sessions[0].send_and_wait.assert_awaited_once_with("Prompt", timeout=60.0)
    sdk.sessions[0].disconnect.assert_awaited_once()
    client.stop.assert_awaited_once()


def test_metadata_mapping(sdk):
    sdk.events.append((AssistantUsageData(
        model="reported-model", input_tokens=0, output_tokens=12,
        finish_reason="stop", service_request_id="service-123",
        duration=timedelta(milliseconds=125),
    ), None))
    result = CopilotProvider(model="requested-model", timeout=9).generate("P", task_name="t")
    assert sdk.options[0]["model"] == "requested-model"
    assert result.metadata.model == "reported-model"
    assert result.metadata.usage.input_tokens == 0
    assert result.metadata.usage.output_tokens == 12
    assert result.metadata.finish_reason == "stop"
    assert result.metadata.request_id == "service-123"
    assert result.metadata.latency_ms == 125
    sdk.sessions[0].send_and_wait.assert_awaited_once_with("P", timeout=9)


def test_partial_usage_and_subagent_events(sdk):
    sdk.events.extend([
        (AssistantUsageData(model="ignored", input_tokens=999), "subagent"),
        (AssistantUsageData(model="actual", output_tokens=4), None),
    ])
    metadata = CopilotProvider().generate("P", task_name="t").metadata
    assert metadata.model == "actual"
    assert metadata.usage.input_tokens is None
    assert metadata.usage.output_tokens == 4
    assert metadata.request_id is None


def test_multiple_usage_events_do_not_invent_partial_totals(sdk):
    sdk.events.extend([
        (AssistantUsageData(model="m", input_tokens=10, output_tokens=2), None),
        (AssistantUsageData(model="m", input_tokens=20), None),
    ])
    metadata = CopilotProvider().generate("P", task_name="t").metadata
    assert metadata.usage.input_tokens == 30
    assert metadata.usage.output_tokens is None
    assert metadata.latency_ms is None


@pytest.mark.parametrize("content", [None, "", " \n\t"])
def test_empty_response_cleans_up(sdk, monkeypatch, content):
    original = copilot_provider.CopilotClient

    def factory(**kwargs):
        client = original(**kwargs)
        sdk.sessions[-1].send_and_wait.return_value = (
            None if content is None else SimpleNamespace(data=SimpleNamespace(content=content))
        )
        return client

    monkeypatch.setattr(copilot_provider, "CopilotClient", factory)
    with pytest.raises((ValueError, ValidationError)):
        CopilotProvider().generate("P", task_name="t")
    sdk.sessions[0].disconnect.assert_awaited_once()
    sdk.clients[0][0].stop.assert_awaited_once()


@pytest.mark.parametrize("stage", ["create", "send", "timeout", "disconnect", "stop"])
def test_sdk_failures_propagate_and_cleanup_is_attempted(sdk, monkeypatch, stage):
    original = copilot_provider.CopilotClient
    failure = TimeoutError("SDK failure") if stage == "timeout" else RuntimeError("SDK failure")

    def factory(**kwargs):
        client = original(**kwargs)
        target = {
            "create": client.create_session,
            "send": sdk.sessions[-1].send_and_wait,
            "timeout": sdk.sessions[-1].send_and_wait,
            "disconnect": sdk.sessions[-1].disconnect,
            "stop": client.stop,
        }[stage]
        target.side_effect = failure
        return client

    monkeypatch.setattr(copilot_provider, "CopilotClient", factory)
    with pytest.raises((RuntimeError, TimeoutError), match="SDK failure"):
        CopilotProvider().generate("P", task_name="t")
    client, kwargs = sdk.clients[0]
    client.stop.assert_awaited_once()
    if stage != "create":
        sdk.sessions[0].disconnect.assert_awaited_once()
    if stage == "stop":
        client.force_stop.assert_awaited_once()
    assert not Path(kwargs["base_directory"]).exists()


def test_session_isolation_and_calls_from_running_loop(sdk):
    provider = CopilotProvider()
    provider.generate("First", task_name="same")

    async def call():
        return provider.generate("Second", task_name="same")

    asyncio.run(call())
    assert len(sdk.clients) == len(sdk.sessions) == 2
    assert sdk.clients[0][1]["base_directory"] != sdk.clients[1][1]["base_directory"]
    for session in sdk.sessions:
        session.disconnect.assert_awaited_once()


def test_empty_prompt_does_not_start_sdk(sdk):
    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        CopilotProvider().generate("  ", task_name="t")
    assert sdk.clients == []


@pytest.mark.parametrize("kwargs", [
    {"model": ""}, {"model": " "}, {"timeout": 0}, {"timeout": -1},
    {"timeout": float("inf")}, {"timeout": float("nan")},
])
def test_invalid_configuration(sdk, kwargs):
    with pytest.raises(ValueError):
        CopilotProvider(**kwargs)
    assert sdk.clients == []


def test_requested_model_is_not_fabricated_as_reported_metadata(sdk):
    result = CopilotProvider(model="requested").generate("P", task_name="t")
    assert sdk.options[0]["model"] == "requested"
    assert result.metadata.model is None
