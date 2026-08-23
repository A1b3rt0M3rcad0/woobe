from __future__ import annotations

import asyncio
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.infra.execution.ask_agent_stream_service import (
    AskAgentStreamService,
)
from modules.agent.infra.database.models import AgentOutboxEventModel
from modules.observability.infra.database.models import TraceEventModel, TraceModel
from modules.observability.infra.messaging.truthful_trace_projector import (
    project_agent_event,
)
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


class BlockingStreamService(AskAgentStreamService):
    def __init__(
        self,
        engine,
        *,
        trace_id: UUID,
        session_id: UUID,
    ) -> None:
        self._engine = engine
        self._trace_id = trace_id
        self._session_id = session_id

    async def _run_execution(self, input_dto, channel):
        channel.bind_execution(
            trace_id=self._trace_id,
            session_id=self._session_id,
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
        )
        await channel.emit(
            "meta",
            trace_id=str(self._trace_id),
            session_id=str(self._session_id),
            project_id=str(input_dto.project_id),
            agent_id=str(input_dto.agent_id),
        )
        await asyncio.Event().wait()


def _sse_payload(frame: str) -> dict:
    for line in frame.splitlines():
        if line.startswith("data:"):
            return json.loads(line.removeprefix("data:").strip())
    raise AssertionError("SSE frame has no data payload")


@pytest.mark.asyncio
async def test_client_disconnect_persists_cancellation_and_projects_cancelled_trace() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    trace_id = uuid4()
    service = BlockingStreamService(
        engine,
        trace_id=trace_id,
        session_id=session_id,
    )
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent_id,
        session_id=session_id,
        message="cancel this request",
    )

    disconnect_checks = 0

    async def is_disconnected() -> bool:
        nonlocal disconnect_checks
        disconnect_checks += 1
        return disconnect_checks >= 2

    frames = [
        frame async for frame in service.stream(
            input_dto,
            disconnect_check=is_disconnected,
        )
    ]

    assert len(frames) == 2
    meta = _sse_payload(frames[0])
    cancelled = _sse_payload(frames[1])
    assert meta["type"] == "meta"
    assert meta["trace_id"] == str(trace_id)
    assert cancelled["type"] == "cancelled"
    assert cancelled["reason"] == "client_disconnected"

    cancellation_filter = (
        AgentOutboxEventModel.event_type == "agent.execution.cancelled.v1",
        AgentOutboxEventModel.payload["trace_id"].astext == str(trace_id),
    )

    try:
        async with session_factory() as session:
            outbox = (
                await session.execute(
                    select(AgentOutboxEventModel).where(*cancellation_filter)
                )
            ).scalar_one()
            assert outbox.payload["trace_id"] == str(trace_id)
            assert outbox.payload["agent_id"] == str(agent_id)
            assert outbox.payload["request_id"]
            assert outbox.payload["reason"] == "client_disconnected"

            await project_agent_event(
                event_type=outbox.event_type,
                payload=outbox.payload,
                session=session,
            )
            await session.commit()

        async with session_factory() as session:
            trace = await session.get(TraceModel, trace_id)
            assert trace is not None
            assert trace.status == "cancelled"
            assert trace.ended_at is not None
            assert trace.data["last_event_type"] == "agent.execution.cancelled.v1"
            assert trace.data["cancellation_reason"] == "client_disconnected"

            event = (
                await session.execute(
                    select(TraceEventModel).where(
                        TraceEventModel.trace_id == trace_id,
                        TraceEventModel.event_type == "warning",
                    )
                )
            ).scalar_one()
            assert event.payload["event"] == "agent.execution.cancelled.v1"
            assert event.payload["reason"] == "client_disconnected"
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(TraceEventModel).where(TraceEventModel.trace_id == trace_id)
            )
            await session.execute(delete(TraceModel).where(TraceModel.id == trace_id))
            await session.execute(
                delete(AgentOutboxEventModel).where(*cancellation_filter)
            )
            await session.commit()
        await engine.dispose()
