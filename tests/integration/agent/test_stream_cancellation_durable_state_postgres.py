from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.infra.database.models import (
    AgentModel,
    AgentOutboxEventModel,
    MessageModel,
    SessionModel,
)
from modules.agent.infra.database.run_models import AgentRunModel
from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import RuntimeStreamChannel
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


@pytest.mark.asyncio
async def test_cancelled_stateful_run_preserves_user_and_partial_assistant_in_postgres() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    user_message_id = uuid4()
    run_id = uuid4()
    trace_id = uuid4()
    started_at = datetime.now(timezone.utc)

    try:
        async with session_factory() as session:
            async with session.begin():
                session.add(
                    AgentModel(
                        id=agent_id,
                        project_id=project_id,
                        provider_credential_id=None,
                        fallback_credential_id=None,
                        name="cancel-persistence-agent",
                        description="",
                        type="assistant",
                        system_prompt="",
                        provider="openai",
                        model="test",
                        fallback_provider=None,
                        fallback_model=None,
                        temperature=0.2,
                        max_output_tokens=256,
                        session_mode="stateful",
                        status="active",
                        settings={},
                    )
                )
            async with session.begin():
                session.add(
                    SessionModel(
                        id=session_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        runtime_environment="draft",
                        opened_release_id=None,
                        chat_surface_id=None,
                        origin="playground",
                        external_session_id=None,
                        tenant_id=None,
                        user_id=None,
                        status="active",
                        mode="chat",
                        data={"source": "test"},
                        last_message_at=started_at,
                    )
                )
            async with session.begin():
                session.add(
                    MessageModel(
                        id=user_message_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        session_id=session_id,
                        role="user",
                        content="write a long answer",
                        input_tokens=None,
                        output_tokens=None,
                        cost_usd=None,
                        data=None,
                    )
                )
            async with session.begin():
                session.add(
                    AgentRunModel(
                        id=run_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        session_id=session_id,
                        agent_release_id=None,
                        input_message_id=user_message_id,
                        output_message_id=None,
                        trace_id=trace_id,
                        environment="draft",
                        origin="playground",
                        status="running",
                        input_message="write a long answer",
                        execution_snapshot={},
                        usage=None,
                        result=None,
                        failure_code=None,
                        failure_detail=None,
                        network_execution_id=None,
                        network_invocation_id=None,
                        parent_run_id=None,
                        rerun_of_run_id=None,
                        started_at=started_at,
                        completed_at=None,
                    )
                )

        transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))
        service = AskAgentStreamService(
            SimpleNamespace(),
            transactions,
            state_store=InMemoryExecutionStateStore(),
        )
        channel = RuntimeStreamChannel()
        channel.bind_execution(
            trace_id=trace_id,
            session_id=session_id,
            project_id=project_id,
            agent_id=agent_id,
        )
        setattr(channel, "run_id", run_id)
        channel.public_output = "partial answer already streamed"
        channel.latest_usage = {
            "input_tokens": 17,
            "output_tokens": 5,
            "total_tokens": 22,
        }
        input_dto = AskInput(
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            message="write a long answer",
            execution_context="playground",
        )

        persisted = await service._persist_cancelled(
            channel,
            input_dto,
            "cancel_requested",
        )

        assert persisted is True

        async with session_factory() as session:
            run = await session.get(AgentRunModel, run_id)
            assert run is not None
            assert run.status == "cancelled"
            assert run.input_message_id == user_message_id
            assert run.result is not None
            assert run.result["answer"] == "partial answer already streamed"
            assert run.result["partial"] is True
            assert run.result["cancelled"] is True
            assert run.completed_at is not None

            messages = list(
                (
                    await session.scalars(
                        select(MessageModel)
                        .where(MessageModel.session_id == session_id)
                        .order_by(MessageModel.created_at.asc(), MessageModel.id.asc())
                    )
                ).all()
            )
            assert [(message.role, message.content) for message in messages] == [
                ("user", "write a long answer"),
                ("assistant", "partial answer already streamed"),
            ]
            assert messages[1].data is not None
            assert messages[1].data["cancelled"] is True
            assert messages[1].data["partial"] is True
            assert messages[1].data["run_id"] == str(run_id)
    finally:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    delete(AgentOutboxEventModel).where(
                        AgentOutboxEventModel.payload["run_id"].astext == str(run_id)
                    )
                )
                await session.execute(delete(AgentRunModel).where(AgentRunModel.id == run_id))
                await session.execute(delete(MessageModel).where(MessageModel.session_id == session_id))
                await session.execute(delete(SessionModel).where(SessionModel.id == session_id))
                await session.execute(delete(AgentModel).where(AgentModel.id == agent_id))
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancel_before_first_token_keeps_user_without_empty_assistant_message() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    user_message_id = uuid4()
    run_id = uuid4()
    trace_id = uuid4()
    started_at = datetime.now(timezone.utc)

    try:
        async with session_factory() as session:
            async with session.begin():
                session.add(
                    AgentModel(
                        id=agent_id,
                        project_id=project_id,
                        provider_credential_id=None,
                        fallback_credential_id=None,
                        name="cancel-before-token-agent",
                        description="",
                        type="assistant",
                        system_prompt="",
                        provider="openai",
                        model="test",
                        fallback_provider=None,
                        fallback_model=None,
                        temperature=0.2,
                        max_output_tokens=256,
                        session_mode="stateful",
                        status="active",
                        settings={},
                    )
                )
            async with session.begin():
                session.add(
                    SessionModel(
                        id=session_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        runtime_environment="draft",
                        opened_release_id=None,
                        chat_surface_id=None,
                        origin="playground",
                        external_session_id=None,
                        tenant_id=None,
                        user_id=None,
                        status="active",
                        mode="chat",
                        data={"source": "test"},
                        last_message_at=started_at,
                    )
                )
            async with session.begin():
                session.add(
                    MessageModel(
                        id=user_message_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        session_id=session_id,
                        role="user",
                        content="stop immediately",
                        input_tokens=None,
                        output_tokens=None,
                        cost_usd=None,
                        data=None,
                    )
                )
            async with session.begin():
                session.add(
                    AgentRunModel(
                        id=run_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        session_id=session_id,
                        agent_release_id=None,
                        input_message_id=user_message_id,
                        output_message_id=None,
                        trace_id=trace_id,
                        environment="draft",
                        origin="playground",
                        status="running",
                        input_message="stop immediately",
                        execution_snapshot={},
                        usage=None,
                        result=None,
                        failure_code=None,
                        failure_detail=None,
                        network_execution_id=None,
                        network_invocation_id=None,
                        parent_run_id=None,
                        rerun_of_run_id=None,
                        started_at=started_at,
                        completed_at=None,
                    )
                )

        transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))
        service = AskAgentStreamService(
            SimpleNamespace(),
            transactions,
            state_store=InMemoryExecutionStateStore(),
        )
        channel = RuntimeStreamChannel()
        channel.bind_execution(
            trace_id=trace_id,
            session_id=session_id,
            project_id=project_id,
            agent_id=agent_id,
        )
        setattr(channel, "run_id", run_id)
        input_dto = AskInput(
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            message="stop immediately",
            execution_context="playground",
        )

        persisted = await service._persist_cancelled(
            channel,
            input_dto,
            "cancel_requested",
        )

        assert persisted is True

        async with session_factory() as session:
            run = await session.get(AgentRunModel, run_id)
            assert run is not None
            assert run.status == "cancelled"
            assert run.result is not None
            assert run.result["answer"] == ""
            assert run.result["partial"] is False

            messages = list(
                (
                    await session.scalars(
                        select(MessageModel).where(MessageModel.session_id == session_id)
                    )
                ).all()
            )
            assert [(message.role, message.content) for message in messages] == [
                ("user", "stop immediately")
            ]
    finally:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    delete(AgentOutboxEventModel).where(
                        AgentOutboxEventModel.payload["run_id"].astext == str(run_id)
                    )
                )
                await session.execute(delete(AgentRunModel).where(AgentRunModel.id == run_id))
                await session.execute(delete(MessageModel).where(MessageModel.session_id == session_id))
                await session.execute(delete(SessionModel).where(SessionModel.id == session_id))
                await session.execute(delete(AgentModel).where(AgentModel.id == agent_id))
        await engine.dispose()
