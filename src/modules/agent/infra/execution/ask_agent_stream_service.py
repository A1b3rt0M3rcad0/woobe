from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput
from modules.agent.domain.runtime_events import AgentExecutionCancelledV1
from modules.agent.infra.adapters.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from modules.agent.infra.adapters.langchain_embedding_factory import (
    LangchainEmbeddingFactory,
)
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.execution.runtime_streaming import (
    RUNTIME_STREAM_HEARTBEAT_SECONDS,
    RuntimeStreamChannel,
    RuntimeStreamEvent,
    current_runtime_stream,
)
from modules.agent.infra.execution.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)
from shared.infra.config import Settings
from shared.security.redaction import redact_text

DisconnectCheck = Callable[[], Awaitable[bool]]


class AskAgentStreamService:
    def __init__(
        self,
        engine: AsyncEngine,
        settings: Settings,
        llm_factory,
        http_executor: HttpToolExecutor | None = None,
    ) -> None:
        self._engine = engine
        self._tool_runtime = AgentToolRuntimeGateway(
            engine,
            settings,
            http_executor,
        )
        self._use_case = StructuredOutputAskAgentUseCase(
            session_factory=engine,
            llm_factory=llm_factory,
            encryption_key=settings.encryption_key,
            tool_executor_factory=self._tool_runtime.execute_tool,
        )
        self._use_case.configure_rag_embedding_factory(LangchainEmbeddingFactory())
        self._use_case.configure_runtime_tool_reader(
            self._tool_runtime.read_runtime_tools
        )

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

        project_id = channel.project_id or input_dto.project_id
        agent_id = channel.agent_id or input_dto.agent_id
        session_id = channel.session_id or input_dto.session_id

        async with AgentUnitOfWork(self._engine) as uow:
            writer = SQLAlchemyAgentOutboxEventWriter(uow)
            event = AgentExecutionCancelledV1.create(
                agent_id=agent_id,
                session_id=session_id,
                payload={
                    "trace_id": str(channel.trace_id),
                    "project_id": str(project_id),
                    "agent_id": str(agent_id),
                    "session_id": str(session_id) if session_id is not None else None,
                    "request_id": str(channel.request_id),
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
                    await self._persist_cancelled(
                        channel,
                        input_dto,
                        "client_disconnected",
                    )
                    yield self._format_event(
                        RuntimeStreamEvent(
                            event_type="cancelled",
                            payload={"reason": "client_disconnected"},
                        )
                    )
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
                    yield self._format_event(
                        RuntimeStreamEvent(
                            event_type="heartbeat",
                            payload={"ts": datetime.now(timezone.utc).isoformat()},
                        )
                    )

                if execution_task.done():
                    if not result_sent:
                        try:
                            result = execution_task.result()
                            yield self._format_event(
                                RuntimeStreamEvent(
                                    event_type="done",
                                    payload=result.model_dump(mode="json"),
                                )
                            )
                        except asyncio.CancelledError:
                            yield self._format_event(
                                RuntimeStreamEvent(
                                    event_type="cancelled",
                                    payload={"reason": "cancelled"},
                                )
                            )
                        except Exception as exc:
                            yield self._format_event(
                                RuntimeStreamEvent(
                                    event_type="error",
                                    payload={"message": redact_text(str(exc))},
                                )
                            )
                    break
        finally:
            if not execution_task.done():
                execution_task.cancel()

    @staticmethod
    def _format_event(event: RuntimeStreamEvent) -> str:
        payload = {"type": event.event_type, **event.payload}
        return (
            f"event: {event.event_type}\n"
            f"data: {json.dumps(payload, default=str)}\n\n"
        )
