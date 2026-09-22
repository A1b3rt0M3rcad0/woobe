from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from modules.agent.entrypoint import (
    AskInput,
    EmptyModelOutputError,
    HttpToolExecutor,
    RuntimeStreamChannel,
    build_internal_agent_runtime,
    current_execution,
    current_runtime_stream,
    new_execution_context,
)
from modules.network.background_boundary import AgentInvocationResult, InternalDelegationTool
from modules.network.background_boundary import (
    NetworkRuntimeFailure,
    classify_runtime_exception,
)
from woobe_workers.settings import WorkerSettings

AgentStreamHandler = Callable[[str, dict[str, Any]], Awaitable[None]]
_NETWORK_EXTERNAL_CONTEXT_OVERRIDE_KEY = "__network_external_context__"


def _caused_by_empty_model_output(exception: Exception) -> bool:
    current: BaseException | None = exception
    seen: set[int] = set()
    while isinstance(current, Exception) and id(current) not in seen:
        if isinstance(current, EmptyModelOutputError):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _is_public_runtime_token(payload: dict[str, Any]) -> bool:
    phase = payload.get("phase")
    return (
        payload.get("visibility") == "assistant"
        and payload.get("channel") == "final"
        and (
            phase in {
                "response_generation",
                "capability_response_generation",
                "final_response_generation",
            }
            or (isinstance(phase, str) and phase.startswith("tool_followup_"))
        )
    )


def _split_runtime_snapshot_override(
    snapshot_override: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(snapshot_override, dict):
        return snapshot_override, None

    runtime_override = dict(snapshot_override)
    raw_external_context = runtime_override.pop(
        _NETWORK_EXTERNAL_CONTEXT_OVERRIDE_KEY,
        None,
    )
    external_context: dict[str, Any] | None = None
    if raw_external_context is not None:
        if not isinstance(raw_external_context, dict):
            raise RuntimeError("Network External Context projection is invalid")
        external_context = dict(raw_external_context)

    return runtime_override or None, external_context


class ProjectRAIAgentInvoker:
    """Outer adapter that lets Network consume the Agent runtime in-process.

    Network owns the AgentInvoker protocol. Cross-bounded-context composition is
    intentionally outside woobe-core, so Network never imports Agent internals.
    """

    def __init__(self, settings: WorkerSettings, http_executor: HttpToolExecutor) -> None:
        self._settings = settings
        self._http_executor = http_executor
        self._use_case = build_internal_agent_runtime(
            self._settings,
            self._http_executor,
        )

    async def invoke(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        release_id: UUID | None,
        snapshot_override: dict[str, Any] | None,
        message: str,
        agent_session_id: UUID | None,
        execution_context: str,
        internal_tools: list[InternalDelegationTool],
        network_context: dict[str, object],
        stream_handler: AgentStreamHandler | None = None,
    ) -> AgentInvocationResult:
        internal_handlers = {tool.id: tool.handler for tool in internal_tools}
        runtime_snapshot_override, external_context = _split_runtime_snapshot_override(
            snapshot_override
        )

        context = new_execution_context()
        context.project_id = project_id
        context.agent_id = agent_id
        context.session_id = agent_session_id
        context.execution_context = execution_context
        context.agent_release_id = release_id
        context.internal_tool_definitions = [tool.definition() for tool in internal_tools]
        context.internal_tool_name_to_id = {tool.name: str(tool.id) for tool in internal_tools}
        context.internal_tool_handlers = internal_handlers
        uuid_context_fields = {
            "network_id",
            "network_version_id",
            "network_session_id",
            "network_execution_id",
            "network_invocation_id",
            "parent_invocation_id",
            "network_node_id",
        }
        for key, value in network_context.items():
            if hasattr(context, key):
                if key in uuid_context_fields and value is not None:
                    value = UUID(str(value))
                setattr(context, key, value)

        input_dto = AskInput(
            project_id=project_id,
            agent_id=agent_id,
            message=message,
            session_id=agent_session_id,
            metadata={
                "source": "network_runtime",
                "defer_persistence": True,
                **network_context,
            },
            external_context=external_context,
            execution_context=execution_context,
            loaded_release_id=release_id,
            snapshot_override=runtime_snapshot_override,
        )

        execution_token = current_execution.set(context)
        channel: RuntimeStreamChannel | None = None
        stream_token = None
        streamed_output = False
        execution_task: asyncio.Task[Any] | None = None

        try:
            try:
                if stream_handler is None:
                    output = await self._use_case.execute(input_dto)
                else:
                    channel = RuntimeStreamChannel()
                    stream_token = current_runtime_stream.set(channel)
                    execution_task = asyncio.create_task(self._use_case.execute(input_dto))
                    while True:
                        if execution_task.done() and channel.queue.empty():
                            break
                        try:
                            event = await asyncio.wait_for(channel.queue.get(), timeout=0.1)
                        except asyncio.TimeoutError:
                            continue

                        payload = dict(event.payload)
                        if context.run_id is not None:
                            payload["agent_run_id"] = str(context.run_id)
                        if event.event_type == "token":
                            if not _is_public_runtime_token(payload):
                                continue
                            streamed_output = True
                            await stream_handler("token", payload)
                            continue

                        if event.event_type not in {"done", "error", "cancelled"}:
                            await stream_handler(event.event_type, payload)

                    output = await execution_task
                    output_run_id = getattr(output, "run_id", None) or context.run_id
                    # Guarantee that even a Run with no intermediate public event exposes
                    # the durable Agent Run identity to the parent Network invocation.
                    if output_run_id is not None:
                        await stream_handler(
                            "agent_run_identity",
                            {"agent_run_id": str(output_run_id)},
                        )
            except Exception as exc:
                # Acceptance assigns the Agent Run before model/tool work. Preserve
                # that durable identity even when the child invocation terminates
                # before any public Agent event can be forwarded to Network.
                if stream_handler is not None and context.run_id is not None:
                    await stream_handler(
                        "agent_run_identity",
                        {"agent_run_id": str(context.run_id)},
                    )
                if _caused_by_empty_model_output(exc):
                    failure = NetworkRuntimeFailure(
                        code="empty_model_output",
                        stage="output_validation",
                        safe_message="The Agent completed without producing a public result.",
                        internal_detail=str(exc),
                        retryable=False,
                    )
                else:
                    failure = classify_runtime_exception(exc)
                failure = failure.with_agent_context(
                    trace_id=context.trace_id,
                    agent_session_id=context.session_id,
                )
                raise failure from exc

            output_run_id = getattr(output, "run_id", None) or context.run_id
            usage = output.usage.model_dump() if output.usage else None
            result = AgentInvocationResult(
                answer=output.answer,
                session_id=output.session_id,
                trace_id=output.trace_id,
                provider=output.provider,
                model=output.model,
                usage=usage,
                tool_calls=[item.model_dump() for item in output.tool_calls],
                sources=[item.model_dump() for item in output.sources],
                parsed_output=output.parsed_output,
                output_parse_error=output.output_parse_error,
                execution_events=list(output.execution_events or []),
                streamed_output=streamed_output,
            )
            diagnostics = getattr(output, "diagnostics", None)
            llm_calls = getattr(output, "llm_calls", None)
            object.__setattr__(
                result,
                "diagnostics",
                diagnostics if isinstance(diagnostics, dict) else None,
            )
            object.__setattr__(
                result,
                "llm_calls",
                llm_calls if isinstance(llm_calls, list) else [],
            )
            object.__setattr__(result, "run_id", output_run_id)
            object.__setattr__(result, "started_at", getattr(output, "run_started_at", None))
            object.__setattr__(result, "completed_at", getattr(output, "run_completed_at", None))
            return result
        finally:
            if execution_task is not None and not execution_task.done():
                execution_task.cancel()
            if stream_token is not None:
                current_runtime_stream.reset(stream_token)
            current_execution.reset(execution_token)