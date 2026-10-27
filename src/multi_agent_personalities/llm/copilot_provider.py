"""Stateless synchronous text generation through GitHub Copilot SDK 1.0.26."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory

from copilot import CopilotClient
from copilot.rpc import PermissionDecisionReject
from copilot.session_events import AssistantUsageData, SessionEvent, SessionEventType

from multi_agent_personalities.models import (
    GenerationMetadata,
    GenerationResult,
    TokenUsage,
)


class CopilotProvider:
    """Use ambient GitHub authentication; each call owns its SDK resources.

    No client, subprocess, or authentication operation starts until generate().
    Calls block, including when invoked from an existing asyncio event loop.
    The SDK default model is selected when model is omitted. No retries are
    performed by this adapter; SDK-internal retries are not observable here.
    """

    def __init__(self, model: str | None = None, *, timeout: float = 60.0) -> None:
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise ValueError("Model cannot be empty")
        if not 0 < timeout < float("inf"):
            raise ValueError("Timeout must be finite and positive")
        self._model = model
        self._timeout = timeout

    def generate(self, prompt: str, *, task_name: str) -> GenerationResult:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._generate(prompt))
        # SDK objects and their event loop stay together in the worker thread.
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(self._generate(prompt))).result()

    async def _generate(self, prompt: str) -> GenerationResult:
        usage_events: list[AssistantUsageData] = []

        def on_event(event: SessionEvent) -> None:
            if (
                event.type == SessionEventType.ASSISTANT_USAGE
                and not event.agent_id
                and isinstance(event.data, AssistantUsageData)
            ):
                usage_events.append(event.data)

        # Empty mode disables instructions, plugins, memory, skills, hooks,
        # host git operations and telemetry. Its storage must be explicit.
        # A temporary home also prevents session data from surviving the call.
        with TemporaryDirectory(prefix="copilot-generation-") as directory:
            client = CopilotClient(
                mode="empty", base_directory=directory, use_logged_in_user=True,
            )
            try:
                options = {} if self._model is None else {"model": self._model}
                session = await client.create_session(
                    **options,
                    available_tools=[],
                    on_permission_request=lambda *_: PermissionDecisionReject(),
                    enable_config_discovery=False,
                    mcp_servers={},
                    custom_agents=[],
                    infinite_sessions={"enabled": False},
                    streaming=False,
                    on_event=on_event,
                )
                try:
                    response = await session.send_and_wait(prompt, timeout=self._timeout)
                    if response is None:
                        raise ValueError("Copilot returned no assistant response")
                    # Usage is per API call. Aggregate only counters present on
                    # every call; never present partial totals as complete usage.
                    def total(field: str) -> int | None:
                        values = [getattr(item, field) for item in usage_events]
                        return sum(values) if values and all(v is not None for v in values) else None

                    input_tokens = total("input_tokens")
                    output_tokens = total("output_tokens")
                    last = usage_events[-1] if usage_events else None
                    return GenerationResult(
                        text=response.data.content,
                        metadata=GenerationMetadata(
                            provider="copilot",
                            model=last.model if last else None,
                            usage=TokenUsage(
                                input_tokens=input_tokens, output_tokens=output_tokens,
                            ) if input_tokens is not None or output_tokens is not None else None,
                            finish_reason=last.finish_reason if last else None,
                            request_id=last.service_request_id if last else None,
                            latency_ms=(last.duration.total_seconds() * 1000)
                            if last and last.duration is not None and len(usage_events) == 1
                            else None,
                        ),
                    )
                finally:
                    await session.disconnect()
            finally:
                try:
                    await client.stop()
                except BaseException:
                    await client.force_stop()
                    raise
