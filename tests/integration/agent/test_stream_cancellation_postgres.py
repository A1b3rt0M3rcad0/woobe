from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.infra.database.models import AgentOutboxEventModel
from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import RuntimeStreamChannel
from modules.observability.infra.database.models import TraceEventModel, TraceModel
from modules.observability.infra.messaging.truthful_trace_projector import project_agent_event
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


@pytest.mark.asyncio
async def test_explicit_cancel_projects_cancelled_trace_without_transport_semantics() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    trace_id = uuid4()
    transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))
    service = AskAgentStreamService(
        MagicMock(),
        transactions,
        state_store=InMemoryExecutionStateStore(),
    )
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent_id,
        session_id=session_id,
        message="cancel this request",
    )
    channel = RuntimeStreamChannel()
    channel.bind_execution(
        trace_id=trace_id,
        session_id=session_id,
        project_id=project_id,
        agent_id=agent_id,
    )

    persisted = await service._persist_cancelled(
        channel,
        input_dto,
        "cancel_requested",
    )
    assert persisted is True

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
            assert outbox.payload["reason"] == "cancel_requested"

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
            assert trace.data["cancellation_reason"] == "cancel_requested"

            event = (
                await session.execute(
                    select(TraceEventModel).where(
                        TraceEventModel.trace_id == trace_id,
                        TraceEventModel.event_type == "warning",
                    )
                )
            ).scalar_one()
            assert event.payload["event"] == "agent.execution.cancelled.v1"
            assert event.payload["reason"] == "cancel_requested"
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
