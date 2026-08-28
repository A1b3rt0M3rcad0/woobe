from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete

from modules.agent.domain.run import AgentRunStatus
from modules.agent.infra.database.models import AgentModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


async def _seed_run(session_factory, *, project_id, agent_id, run_id, trace_id, status: str) -> None:
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
            terminal = status != "running"
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
                    input_message="cancel won first",
                    execution_snapshot={},
                    usage=(
                        {"input_tokens": 3, "output_tokens": 1, "total_tokens": 4}
                        if terminal
                        else None
                    ),
                    result=(
                        {"answer": "partial", "cancelled": True, "partial": True}
                        if status == "cancelled"
                        else None
                    ),
                    failure_code=None,
                    failure_detail=None,
                    network_execution_id=None,
                    network_invocation_id=None,
                    parent_run_id=None,
                    rerun_of_run_id=None,
                    started_at=now,
                    completed_at=now if terminal else None,
                )
            )


async def _cleanup(session_factory, *, run_id, agent_id) -> None:
    async with session_factory() as session:
        async with session.begin():
            await session.execute(delete(AgentRunModel).where(AgentRunModel.id == run_id))
            await session.execute(delete(AgentModel).where(AgentModel.id == agent_id))


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
        )
        transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))

        async def late_completion(repositories, _outbox):
            run = await repositories.runs.get_by_id(run_id)
            assert run is not None
            run.status = AgentRunStatus.COMPLETED
            run.result = {"answer": "late provider answer"}
            run.completed_at = datetime.now(timezone.utc)
            saved = await repositories.runs.save(run)
            assert saved.status == AgentRunStatus.CANCELLED
            assert saved.result is not None
            assert saved.result["cancelled"] is True

        await transactions.run(late_completion)

        async with session_factory() as session:
            persisted = await session.get(AgentRunModel, run_id)
            assert persisted is not None
            assert persisted.status == "cancelled"
            assert persisted.result["answer"] == "partial"
            assert persisted.result["cancelled"] is True
            assert persisted.result["partial"] is True
    finally:
        await _cleanup(session_factory, run_id=run_id, agent_id=agent_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_stale_completion_transaction_refreshes_after_concurrent_cancel_commit() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    agent_id = uuid4()
    run_id = uuid4()
    trace_id = uuid4()
    stale_loaded = asyncio.Event()
    cancellation_committed = asyncio.Event()

    try:
        await _seed_run(
            session_factory,
            project_id=project_id,
            agent_id=agent_id,
            run_id=run_id,
            trace_id=trace_id,
            status="running",
        )
        completion_transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))
        cancellation_transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))

        async def late_completion(repositories, _outbox):
            run = await repositories.runs.get_by_id(run_id)
            assert run is not None
            assert run.status == AgentRunStatus.RUNNING
            stale_loaded.set()
            await asyncio.wait_for(cancellation_committed.wait(), timeout=2)
            run.status = AgentRunStatus.COMPLETED
            run.result = {"answer": "late completion"}
            run.completed_at = datetime.now(timezone.utc)
            saved = await repositories.runs.save(run)
            assert saved.status == AgentRunStatus.CANCELLED
            assert saved.result is not None
            assert saved.result["answer"] == "cancelled winner"

        completion_task = asyncio.create_task(completion_transactions.run(late_completion))
        await asyncio.wait_for(stale_loaded.wait(), timeout=2)

        async def cancel_winner(repositories, _outbox):
            run = await repositories.runs.get_by_id_for_update(run_id)
            assert run is not None
            assert run.status == AgentRunStatus.RUNNING
            run.status = AgentRunStatus.CANCELLED
            run.result = {
                "answer": "cancelled winner",
                "cancelled": True,
                "partial": True,
            }
            run.completed_at = datetime.now(timezone.utc)
            saved = await repositories.runs.save(run)
            assert saved.status == AgentRunStatus.CANCELLED

        await cancellation_transactions.run(cancel_winner)
        cancellation_committed.set()
        await asyncio.wait_for(completion_task, timeout=2)

        async with session_factory() as session:
            persisted = await session.get(AgentRunModel, run_id)
            assert persisted is not None
            assert persisted.status == "cancelled"
            assert persisted.result["answer"] == "cancelled winner"
            assert persisted.result["cancelled"] is True
    finally:
        cancellation_committed.set()
        await _cleanup(session_factory, run_id=run_id, agent_id=agent_id)
        await engine.dispose()
