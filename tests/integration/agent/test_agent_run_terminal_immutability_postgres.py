from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from modules.agent.domain.events import AgentExecutionCompletedV1
from modules.agent.domain.run import AgentRunStatus
from modules.agent.infra.database.agent_run_repository import AgentRunTerminalConflict
from modules.agent.infra.database.models import AgentModel, AgentOutboxEventModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


async def _cleanup(session_factory, *, run_id, agent_id) -> None:
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                delete(AgentOutboxEventModel).where(
                    AgentOutboxEventModel.payload["run_id"].astext == str(run_id)
                )
            )
            await session.execute(delete(AgentRunModel).where(AgentRunModel.id == run_id))
            await session.execute(delete(AgentModel).where(AgentModel.id == agent_id))


async def _seed_run(
    session_factory,
    *,
    project_id,
    agent_id,
    run_id,
    trace_id,
    status: str,
    result: dict | None,
) -> None:
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        async with session.begin():
            session.add(
                AgentModel(
                    id=agent_id,
                    project_id=project_id,
                    provider_credential_id=None,
                    fallback_credential_id=None,
                    name="terminal-immutability-agent",
                    description="",
                    type="assistant",
                    system_prompt="",
                    provider="openai",
                    model="test",
                    fallback_provider=None,
                    fallback_model=None,
                    temperature=0.2,
                    max_output_tokens=128,
                    session_mode="stateless",
                    status="active",
                    settings={},
                )
            )
        async with session.begin():
            session.add(
                AgentRunModel(
                    id=run_id,
                    project_id=project_id,
                    agent_id=agent_id,
                    session_id=None,
                    agent_release_id=None,
                    input_message_id=None,
                    output_message_id=None,
                    trace_id=trace_id,
                    environment="draft",
                    origin="runtime_api",
                    status=status,
                    input_message="terminal race",
                    execution_snapshot={},
                    usage={"input_tokens": 3, "output_tokens": 1, "total_tokens": 4},
                    result=result,
                    failure_code=None,
                    failure_detail=None,
                    network_execution_id=None,
                    network_invocation_id=None,
                    parent_run_id=None,
                    rerun_of_run_id=None,
                    started_at=now,
                    completed_at=None if status == "running" else now,
                )
            )


@pytest.mark.asyncio
async def test_late_completed_save_cannot_overwrite_cancelled_agent_run() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    agent_id = uuid4()
    run_id = uuid4()
    trace_id = uuid4()

    try:
        await _seed_run(
            session_factory,
            project_id=project_id,
            agent_id=agent_id,
            run_id=run_id,
            trace_id=trace_id,
            status="cancelled",
            result={"answer": "partial", "cancelled": True, "partial": True},
        )
        transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))

        async def late_completion(repositories, outbox):
            await outbox.write(
                AgentExecutionCompletedV1.create(
                    agent_id=agent_id,
                    session_id=None,
                    payload={"run_id": str(run_id), "trace_id": str(trace_id), "answer": "late provider answer"},
                )
            )
            run = await repositories.runs.get_by_id(run_id)
            assert run is not None
            run.status = AgentRunStatus.COMPLETED
            run.result = {"answer": "late provider answer"}
            run.completed_at = datetime.now(timezone.utc)
            await repositories.runs.save(run)

        with pytest.raises(AgentRunTerminalConflict) as exc_info:
            await transactions.run(late_completion)

        assert exc_info.value.persisted_status == AgentRunStatus.CANCELLED.value
        assert exc_info.value.incoming_status == AgentRunStatus.COMPLETED.value

        async with session_factory() as session:
            persisted = await session.get(AgentRunModel, run_id)
            assert persisted is not None
            assert persisted.status == "cancelled"
            assert persisted.result["answer"] == "partial"
            losing_completion_events = list((await session.scalars(
                select(AgentOutboxEventModel).where(
                    AgentOutboxEventModel.payload["run_id"].astext == str(run_id),
                    AgentOutboxEventModel.event_type == "agent.execution.completed.v1",
                )
            )).all())
            assert losing_completion_events == []
    finally:
        await _cleanup(session_factory, run_id=run_id, agent_id=agent_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_completed_writer_rolls_back_its_outbox_side_effects() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    agent_id = uuid4()
    run_id = uuid4()
    trace_id = uuid4()

    try:
        await _seed_run(
            session_factory,
            project_id=project_id,
            agent_id=agent_id,
            run_id=run_id,
            trace_id=trace_id,
            status="completed",
            result={"answer": "canonical answer"},
        )
        transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))

        async def duplicate_completion(repositories, outbox):
            await outbox.write(
                AgentExecutionCompletedV1.create(
                    agent_id=agent_id,
                    session_id=None,
                    payload={"run_id": str(run_id), "trace_id": str(trace_id), "answer": "duplicate answer"},
                )
            )
            run = await repositories.runs.get_by_id(run_id)
            assert run is not None
            run.status = AgentRunStatus.COMPLETED
            run.result = {"answer": "duplicate answer"}
            await repositories.runs.save(run)

        with pytest.raises(AgentRunTerminalConflict) as exc_info:
            await transactions.run(duplicate_completion)

        assert exc_info.value.persisted_status == AgentRunStatus.COMPLETED.value
        assert exc_info.value.incoming_status == AgentRunStatus.COMPLETED.value

        async with session_factory() as session:
            persisted = await session.get(AgentRunModel, run_id)
            assert persisted is not None
            assert persisted.result["answer"] == "canonical answer"
            duplicate_events = list((await session.scalars(
                select(AgentOutboxEventModel).where(
                    AgentOutboxEventModel.payload["run_id"].astext == str(run_id)
                )
            )).all())
            assert duplicate_events == []
    finally:
        await _cleanup(session_factory, run_id=run_id, agent_id=agent_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_cancel_and_completion_have_one_postgres_winner_and_rollback_loser() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    agent_id = uuid4()
    run_id = uuid4()
    trace_id = uuid4()
    cancel_locked = asyncio.Event()
    completion_staged = asyncio.Event()

    try:
        await _seed_run(
            session_factory,
            project_id=project_id,
            agent_id=agent_id,
            run_id=run_id,
            trace_id=trace_id,
            status="running",
            result=None,
        )
        transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))

        async def cancel_writer(repositories, _outbox):
            run = await repositories.runs.get_by_id_for_update(run_id)
            assert run is not None
            cancel_locked.set()
            await asyncio.wait_for(completion_staged.wait(), timeout=2)
            run.status = AgentRunStatus.CANCELLED
            run.result = {"answer": "partial", "partial": True, "cancelled": True}
            run.completed_at = datetime.now(timezone.utc)
            await repositories.runs.save(run)

        async def completion_writer(repositories, outbox):
            await asyncio.wait_for(cancel_locked.wait(), timeout=2)
            run = await repositories.runs.get_by_id(run_id)
            assert run is not None
            assert run.status == AgentRunStatus.RUNNING
            await outbox.write(
                AgentExecutionCompletedV1.create(
                    agent_id=agent_id,
                    session_id=None,
                    payload={"run_id": str(run_id), "trace_id": str(trace_id), "answer": "losing completion"},
                )
            )
            completion_staged.set()
            run.status = AgentRunStatus.COMPLETED
            run.result = {"answer": "losing completion"}
            run.completed_at = datetime.now(timezone.utc)
            await repositories.runs.save(run)

        cancel_task = asyncio.create_task(transactions.run(cancel_writer))
        completion_task = asyncio.create_task(transactions.run(completion_writer))
        await cancel_task
        with pytest.raises(AgentRunTerminalConflict) as exc_info:
            await completion_task

        assert exc_info.value.persisted_status == AgentRunStatus.CANCELLED.value
        assert exc_info.value.incoming_status == AgentRunStatus.COMPLETED.value

        async with session_factory() as session:
            persisted = await session.get(AgentRunModel, run_id)
            assert persisted is not None
            assert persisted.status == "cancelled"
            assert persisted.result["answer"] == "partial"
            losing_events = list((await session.scalars(
                select(AgentOutboxEventModel).where(
                    AgentOutboxEventModel.payload["run_id"].astext == str(run_id),
                    AgentOutboxEventModel.event_type == "agent.execution.completed.v1",
                )
            )).all())
            assert losing_events == []
    finally:
        await _cleanup(session_factory, run_id=run_id, agent_id=agent_id)
        await engine.dispose()
