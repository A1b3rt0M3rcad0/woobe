from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timezone
from uuid import UUID

from modules.agent.application.composers.tool_runtime_factory import build_tool_runtime_registry
from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput
from modules.agent.application.dtos.tools_dtos import ExecuteToolInput
from modules.agent.application.runtime_tool_inventory import (
    execute_runtime_tool_inventory,
    is_runtime_tool_inventory_id,
)
from modules.agent.application.runtime_tool_use_cases import RuntimeExecuteToolUseCase
from modules.agent.application.tool_release_snapshots import tool_from_release_snapshot
from modules.agent.application.tool_runtime import MCP_AGENT_SESSION_INPUT_KEY
from modules.agent.application.use_cases.execution_context import current_execution
from modules.agent.application.use_cases.runtime_streaming import (
    RUNTIME_STREAM_HEARTBEAT_SECONDS,
    RuntimeStreamChannel,
    RuntimeStreamEvent,
    current_runtime_stream,
)
from modules.agent.application.use_cases.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)
from modules.agent.domain.runtime_events import AgentExecutionCancelledV1
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config import Settings
from shared.observability.metrics import runtime_metrics
from shared.security.redaction import redact_text

logger = logging.getLogger(__name__)
DisconnectCheck = Callable[[], Awaitable[bool]]


class AskAgentStreamService:
    def __init__(
        self,
        session_factory,
        llm_factory,
        http_executor: HttpToolExecutor | None = None,
    ) -> None:
        self._session_factory = session_factory
        settings = Settings.model_validate({})
        self._settings = settings
        self._cipher = SecretCipherAdapter(settings.encryption_key)
        self._http_executor = http_executor
        self._use_case = StructuredOutputAskAgentUseCase(
            session_factory=session_factory,
            llm_factory=llm_factory,
            encryption_key=settings.encryption_key,
            tool_executor_factory=self._execute_tool,
        )

    async def _execute_tool(self, tool_id: UUID, input_data: dict) -> dict:
        try:
            if is_runtime_tool_inventory_id(tool_id):
                return execute_runtime_tool_inventory(input_data)

            runtime_input = dict(input_data or {})
            context = current_execution.get()
            if context and context.session_id:
                runtime_input[MCP_AGENT_SESSION_INPUT_KEY] = str(context.session_id)
            snapshot = (
                context.tool_snapshots.get(str(tool_id))
                if context and context.tool_snapshots
                else None
            )

            async with AgentUnitOfWork(self._session_factory) as uow:
                resolver = ToolSecretResolverAdapter(uow.tool_secrets, self._cipher)
                executor = self._http_executor or get_http_tool_executor()
                registry = build_tool_runtime_registry(
                    settings=self._settings,
                    executor=executor,
                    secret_resolver=resolver,
                )
                if snapshot is not None:
                    result = await registry.execute(
                        tool_from_release_snapshot(snapshot),
                        runtime_input,
                    )
                    if not result.success:
                        runtime_metrics.increment_tool_failure(tool=str(tool_id))
                    return {
                        "success": result.success,
                        "output": result.output,
                        "duration_ms": result.duration_ms,
                        "error": result.error,
                    }

                result = await RuntimeExecuteToolUseCase(
                    tool_repo=uow.tools,
                    runtime_registry=registry,
                ).execute(ExecuteToolInput(tool_id=tool_id, input_data=runtime_input))
                if not result.success:
                    runtime_metrics.increment_tool_failure(tool=str(tool_id))
                return result.model_dump()
        except asyncio.CancelledError:
            raise
        except Exception:
            runtime_metrics.increment_tool_failure(tool=str(tool_id))
            raise

    async def _run_execution(
        self,
        input_dto: AskInput,
        channel: RuntimeStreamChannel,
    ) -> AskOutput:
        token = current_runtime_stream.set(channel)
        try:
            return await self._use_case.execute(input_dto)
        finally:
            current_runtime_stream.reset(token)

    async def _persist_cancelled(
        self,
        channel: RuntimeStreamChannel,
        input_dto: AskInput,
        reason: str,
    ) -> None:
        if channel.trace_id is None:
            return
        async with AgentUnitOfWork(self._session_factory) as uow:
            writer = SQLAlchemyAgentOutboxEventWriter(uow)
            event = AgentExecutionCancelledV1.create(
                agent_id=input_dto.agent_id,
                session_id=input_dto.session_id,
                payload={
                    "trace_id": str(channel.trace_id),
                    "reason": reason,
                },
            )
            await writer.write(event)

    async def stream(
        self,
        input_dto: AskInput,
        disconnect_check: DisconnectCheck | None = None,
    ) -> AsyncGenerator[str, None]:
        channel = RuntimeStreamChannel()
        execution_task = asyncio.create_task(self._run_execution(input_dto, channel))
        heartbeat_at = time.monotonic()
        result_sent = False
        try:
            while True:
                if disconnect_check is not None and await disconnect_check():
                    execution_task.cancel()
                    await self._persist_cancelled(channel, input_dto, "client_disconnected")
                    yield self._format_event(RuntimeStreamEvent(event_type="cancelled", payload={"reason": "client_disconnected"}))
                    break

                try:
                    event = await asyncio.wait_for(channel.queue.get(), timeout=0.25)
                    yield self._format_event(event)
                    if event.event_type in {"done", "error", "cancelled"}:
                        result_sent = True
                except asyncio.TimeoutError:
                    pass

                now = time.monotonic()
                if now - heartbeat_at >= RUNTIME_STREAM_HEARTBEAT_SECONDS:
                    heartbeat_at = now
                    yield self._format_event(RuntimeStreamEvent(event_type="heartbeat", payload={"ts": datetime.now(timezone.utc).isoformat()}))

                if execution_task.done():
                    if not result_sent:
                        try:
                            result = execution_task.result()
                            yield self._format_event(RuntimeStreamEvent(event_type="done", payload=result.model_dump(mode="json")))
                        except asyncio.CancelledError:
                            yield self._format_event(RuntimeStreamEvent(event_type="cancelled", payload={"reason": "cancelled"}))
                        except Exception as exc:
                            yield self._format_event(RuntimeStreamEvent(event_type="error", payload={"message": redact_text(str(exc))}))
                    break
        finally:
            if not execution_task.done():
                execution_task.cancel()

    @staticmethod
    def _format_event(event: RuntimeStreamEvent) -> str:
        payload = {"type": event.event_type, **event.payload}
        return f"event: {event.event_type}\ndata: {json.dumps(payload, default=str)}\n\n"
