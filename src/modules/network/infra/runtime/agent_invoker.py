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
from modules.network.application.runtime import AgentInvocationResult, InternalDelegationTool
from modules.network.application.runtime_failures import (
    NetworkRuntimeFailure,
    classify_runtime_exception,
)
from shared.infra.config import Settings

AgentStreamHandler = Callable[[str, dict[str, Any]], Awaitable[None]]
_TOKEN_BATCH_SECONDS = 0.05


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
    # Agent runtime owns the public-output classification. Network transports the
    # contract instead of reinterpreting internal phase names such as tool_followup_1.
    return (
        payload.get("visibility") == "assistant"
        and payload.get("channel") == "final"
    )


def _token_signature(payload: dict[str, Any]) -> tuple[object, object, object]:
    return (
        payload.get("visibility"),
        payload.get("channel"),
        payload.get("phase"),
    )


class ProjectRAIAgentInvoker:
    """Invoke an Agent inside a Network without child PostgreSQL persistence."""

    def __init__(self, settings: Settings, http_executor: HttpToolExecutor) -> None:
        self._settings = settings
        self._http_executor = http_executor
        # The Agent runtime is process-scoped. Per-invocation delegation handlers
        # live in RequestExecutionContext so building a child Run does not rebuild
        # the complete Agent runtime graph.
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
            execution_context=execution_context,
            loaded_release_id=release_id,
            snapshot_override=snapshot_override,
        )

        execution_token = current_execution.set(context)
        channel: RuntimeStreamChannel | None = None
        stream_token = None
        streamed_output = False
        execution_task: asyncio.Task[Any] | None = None
        pending_token: dict[str, Any] | None = None
        pending_signature: tuple[object, object, object] | None = None

        async def flush_token() -> None:
            nonlocal pending_token, pending_signature
            if pending_token is None or stream_handler is None:
                pending_token = None
                pending_signature = None
                return
            payload = pending_token
            pending_token = None
            pending_signature = None
            await stream_handler("token", payload)

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
                        timeout = _TOKEN_BATCH_SECONDS if pending_token is not None else 0.1
                        try:
                            event = await asyncio.wait_for(channel.queue.get(), timeout=timeout)
                        except asyncio.TimeoutError:
                            await flush_token()
                            continue

                        payload = dict(event.payload)
                        if event.event_type == "token":
                            if not _is_public_runtime_token(payload):
                                continue
                            streamed_output = True
                            signature = _token_signature(payload)
                            content = str(payload.get("content") or "")
                            if pending_token is not None and signature == pending_signature:
                                pending_token["content"] = (
                                    str(pending_token.get("content") or "") + content
                                )
                            else:
                                await flush_token()
                                pending_token = payload
                                pending_signature = signature
                            continue

                        # Preserve causal ordering: buffered public tokens must reach
                        # Redis/SSE before any following non-token event.
                        await flush_token()
                        if event.event_type not in {"done", "error", "cancelled"}:
                            await stream_handler(event.event_type, payload)

                    await flush_token()
                    output = await execution_task
            except Exception as exc:
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

            # Usage and v5 telemetry are owned by the Agent runtime. The Network
            # bridge transports them unchanged instead of reconstructing them from
            # RequestExecutionContext internals.
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
            object.__setattr__(result, "started_at", getattr(output, "run_started_at", None))
            object.__setattr__(result, "completed_at", getattr(output, "run_completed_at", None))
            return result
        finally:
            if execution_task is not None and not execution_task.done():
                execution_task.cancel()
            if stream_token is not None:
                current_runtime_stream.reset(stream_token)
            current_execution.reset(execution_token)
