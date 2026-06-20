from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timezone
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput
from modules.agent.application.dtos.tools_dtos import ExecuteToolInput
from modules.agent.application.use_cases.runtime_streaming import (
    RUNTIME_STREAM_HEARTBEAT_SECONDS,
    RuntimeStreamChannel,
    RuntimeStreamEvent,
    current_runtime_stream,
)
from modules.agent.application.use_cases.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)
from modules.agent.application.use_cases.tools_use_cases import ExecuteToolUseCase
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
            async with AgentUnitOfWork(self._session_factory) as uow:
                resolver = ToolSecretResolverAdapter(uow.tool_secrets, self._cipher)
                executor = self._http_executor or get_http_tool_executor()
                result = await ExecuteToolUseCase(
                    tool_repo=uow.tools,
                    tool_executor=executor,
                    secret_resolver=resolver,
                ).execute(ExecuteToolInput(tool_id=tool_id, input_data=input_data))
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
        try:
            async with AgentUnitOfWork(self._session_factory) as uow:
                writer = SQLAlchemyAgentOutboxEventWriter(uow)
                await writer.write(
                    AgentExecutionCancelledV1.create(
                        agent_id=channel.agent_id or input_dto.agent_id,
                        session_id=channel.session_id,
                        payload={
                            "trace_id": str(channel.trace_id),
                            "project_id": str(channel.project_id or input_dto.project_id),
                            "agent_id": str(channel.agent_id or input_dto.agent_id),
                            "session_id": (
                                str(channel.session_id) if channel.session_id else None
                            ),
                            "request_id": str(channel.request_id),
                            "reason": reason,
                        },
                    )
                )
        except Exception as exc:
            logger.warning(
                "Failed to persist runtime cancellation trace_id=%s: %s",
                channel.trace_id,
                redact_text(str(exc)),
            )

    async def _cancel_task(
        self,
        task: asyncio.Task[AskOutput],
        channel: RuntimeStreamChannel,
        input_dto: AskInput,
        reason: str,
    ) -> None:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await self._persist_cancelled(channel, input_dto, reason)
        await channel.emit(
            "cancelled",
            trace_id=str(channel.trace_id) if channel.trace_id else None,
            session_id=str(channel.session_id) if channel.session_id else None,
            reason=reason,
        )

    async def generate(
        self,
        input_dto: AskInput,
        is_disconnected: DisconnectCheck | None = None,
    ) -> AsyncGenerator[str, None]:
        metadata = dict(input_dto.metadata or {})
        metadata.setdefault("server_received_at", datetime.now(timezone.utc).isoformat())
        input_dto = input_dto.model_copy(update={"metadata": metadata})

        channel = RuntimeStreamChannel()
        task = asyncio.create_task(self._run_execution(input_dto, channel))
        last_output = time.monotonic()
        disconnected = False

        try:
            while not task.done() or not channel.queue.empty():
                if is_disconnected is not None:
                    try:
                        disconnected = await is_disconnected()
                    except Exception:
                        disconnected = False
                    if disconnected:
                        await self._cancel_task(
                            task,
                            channel,
                            input_dto,
                            "client_disconnected",
                        )
                        return

                heartbeat_due_in = max(
                    RUNTIME_STREAM_HEARTBEAT_SECONDS - (time.monotonic() - last_output),
                    0.1,
                )
                try:
                    event = await asyncio.wait_for(
                        channel.queue.get(),
                        timeout=min(heartbeat_due_in, 1.0),
                    )
                except TimeoutError:
                    if (
                        not task.done()
                        and time.monotonic() - last_output
                        >= RUNTIME_STREAM_HEARTBEAT_SECONDS
                    ):
                        await channel.emit(
                            "heartbeat",
                            trace_id=str(channel.trace_id) if channel.trace_id else None,
                        )
                    continue

                last_output = time.monotonic()
                yield self._sse_event(event)

            output = await task
            if output.usage is not None:
                await channel.emit(
                    "usage",
                    usage=output.usage.model_dump(),
                    trace_id=str(output.trace_id) if output.trace_id else None,
                )
            await channel.emit(
                "done",
                answer=output.answer,
                session_id=str(output.session_id) if output.session_id else None,
                message_id=str(output.message_id) if output.message_id else None,
                usage=output.usage.model_dump() if output.usage else None,
                sources=[source.model_dump() for source in output.sources],
                tool_calls=[tool.model_dump() for tool in output.tool_calls],
                trace_id=str(output.trace_id) if output.trace_id else None,
                model=output.model,
                provider=output.provider,
                latency_ms=output.latency_ms,
                ttft_ms=channel.ttft_ms,
                fallback_used=output.fallback_used,
                fallback_info=output.fallback_info,
                parsed_output=output.parsed_output,
                output_parse_error=output.output_parse_error,
                execution_events=getattr(output, "execution_events", []),
                diagnostics=getattr(output, "diagnostics", None),
            )
            while not channel.queue.empty():
                yield self._sse_event(channel.queue.get_nowait())
        except asyncio.CancelledError:
            await self._cancel_task(task, channel, input_dto, "stream_cancelled")
            raise
        except Exception as exc:
            logger.exception(
                "Agent streaming execution failed request_id=%s trace_id=%s: %s",
                channel.request_id,
                channel.trace_id,
                redact_text(str(exc)),
            )
            await channel.emit(
                "error",
                code="runtime_execution_failed",
                message="Agent streaming execution failed",
                trace_id=str(channel.trace_id) if channel.trace_id else None,
                session_id=str(channel.session_id) if channel.session_id else None,
            )
            while not channel.queue.empty():
                yield self._sse_event(channel.queue.get_nowait())
        finally:
            if not task.done() and not disconnected:
                await self._cancel_task(task, channel, input_dto, "stream_closed")

    @staticmethod
    def _sse_event(event: RuntimeStreamEvent) -> str:
        payload = {"type": event.event_type, **event.payload}
        return f"data: {json.dumps(payload, default=str)}\n\n"
