from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.execution_strategy_config import (
    execution_strategy_from_runtime_config,
)
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.infra.database.models import AgentModel, AgentOutboxEventModel, SessionModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.execution.agent_run_recovery_runtime import AgentRunRecoveryRuntime
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION
from woobe_workers.consumers.agent.run_recovery_worker import AgentRunRecoveryWorker


class _MissingHotState:
    async def get(self, _run_id):
        return None


class _UnavailableHotState:
    async def get(self, _run_id):
        raise RuntimeError("redis unavailable")


async def _seed(session_factory, *, project_id, agent_id, run_id, trace_id) -> None:
    started_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    session_id = uuid4()
    async with session_factory() as session:
        async with session.begin():
            session.add(
                AgentModel(
                    id=agent_id,
                    project_id=project_id,
                    provider_credential_id=None,
                    fallback_credential_id=None,
                    name="orphan-recovery-agent",
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
                    data={"source": "run_recovery_test"},
                    last_message_at=started_at,
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
                    input_message_id=None,
                    output_message_id=None,
                    trace_id=trace_id,
                    environment="draft",
                    origin="playground",
                    status="running",
                    input_message="orphan me",
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


async def _cleanup(session_factory, *, run_id, agent_id) -> None:
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                delete(AgentOutboxEventModel).where(
                    AgentOutboxEventModel.payload["run_id"].astext == str(run_id)
                )
            )
            await session.execute(delete(AgentRunModel).where(AgentRunModel.id == run_id))
            await session.execute(delete(SessionModel).where(SessionModel.agent_id == agent_id))
            await session.execute(delete(AgentModel).where(AgentModel.id == agent_id))


@pytest.mark.asyncio
async def test_recovery_reads_execution_strategy_from_durable_accepted_snapshot() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    agent_id = uuid4()
    run_id = uuid4()
    trace_id = uuid4()

    try:
        await _seed(
            session_factory,
            project_id=project_id,
            agent_id=agent_id,
            run_id=run_id,
            trace_id=trace_id,
        )
        accepted_snapshot = {
            "agent": {
                "id": str(agent_id),
                "name": "accepted-agent",
                "description": "",
                "behavior_spec": None,
                "system_prompt": "",
                "provider": "openai",
                "model": "accepted-model",
                "provider_model_id": None,
                "provider_credential_id": None,
                "fallback_provider": None,
                "fallback_model": None,
                "fallback_provider_model_id": None,
                "fallback_credential_id": None,
                "temperature": 0.2,
                "max_output_tokens": 128,
                "session_mode": "stateless",
                "settings": {
                    "runtime_config": {
                        "execution_strategy": "standard",
                    }
                },
            }
        }
        async with session_factory() as session:
            async with session.begin():
                agent = await session.get(AgentModel, agent_id)
                run = await session.get(AgentRunModel, run_id)
                assert agent is not None
                assert run is not None
                agent.settings = {
                    "runtime_config": {
                        # Deliberately unsupported in this PR. The mutable Agent state
                        # must not influence recovery once Acceptance froze the Run.
                        "execution_strategy": "react",
                    }
                }
                run.storage_version = EVENT_JOURNAL_STORAGE_VERSION
                run.execution_snapshot = accepted_snapshot

        transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))
        runtime = AgentRunRecoveryRuntime(
            transactions=transactions,
            llm_factory=MagicMock(),
            encryption_key=settings.encryption_key,
        )
        context = new_execution_context()
        context.run_id = run_id
        context.trace_id = trace_id
        context.project_id = project_id
        context.agent_id = agent_id
        context.execution_context = "draft"
        token = current_execution.set(context)
        try:
            accepted = await runtime._read_accepted_run(
                AskInput(
                    project_id=project_id,
                    agent_id=agent_id,
                    message="orphan me",
                    execution_context="draft",
                    metadata={"source": "run_recovery"},
                )
            )
            recovered_agent = AgentRunRecoveryRuntime._apply_accepted_snapshot(
                SimpleNamespace(settings={}),
                accepted,
                context,
            )
        finally:
            current_execution.reset(token)

        async with session_factory() as session:
            mutable_agent = await session.get(AgentModel, agent_id)
            assert mutable_agent is not None
            assert mutable_agent.settings["runtime_config"]["execution_strategy"] == "react"

        runtime_config = recovered_agent.settings["runtime_config"]
        assert runtime_config["execution_strategy"] == "standard"
        assert execution_strategy_from_runtime_config(runtime_config) == "standard"
        assert recovered_agent.model == "accepted-model"
    finally:
        await _cleanup(session_factory, run_id=run_id, agent_id=agent_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_orphaned_standalone_run_without_hot_owner_becomes_uncertain_durably() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    agent_id = uuid4()
    run_id = uuid4()
    trace_id = uuid4()

    try:
        await _seed(session_factory, project_id=project_id, agent_id=agent_id, run_id=run_id, trace_id=trace_id)
        worker = AgentRunRecoveryWorker(
            async_engine=engine,
            state_store=_MissingHotState(),
            stale_after_seconds=60,
        )

        await worker.run()

        async with session_factory() as session:
            run = await session.get(AgentRunModel, run_id)
            assert run is not None
            assert run.status == "uncertain"
            assert run.failure_code == "runtime_state_lost"
            assert run.completed_at is not None
            events = list((await session.scalars(
                select(AgentOutboxEventModel).where(
                    AgentOutboxEventModel.payload["run_id"].astext == str(run_id)
                )
            )).all())
            assert len(events) == 1
            assert events[0].event_type == "agent.execution.failed.v1"
            assert events[0].payload["uncertain"] is True
    finally:
        await _cleanup(session_factory, run_id=run_id, agent_id=agent_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_recovery_does_not_infer_orphan_when_hot_state_backend_is_unavailable() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    agent_id = uuid4()
    run_id = uuid4()
    trace_id = uuid4()

    try:
        await _seed(session_factory, project_id=project_id, agent_id=agent_id, run_id=run_id, trace_id=trace_id)
        worker = AgentRunRecoveryWorker(
            async_engine=engine,
            state_store=_UnavailableHotState(),
            stale_after_seconds=60,
        )

        await worker.run()

        async with session_factory() as session:
            run = await session.get(AgentRunModel, run_id)
            assert run is not None
            assert run.status == "running"
            assert run.completed_at is None
            events = list((await session.scalars(
                select(AgentOutboxEventModel).where(
                    AgentOutboxEventModel.payload["run_id"].astext == str(run_id)
                )
            )).all())
            assert events == []
    finally:
        await _cleanup(session_factory, run_id=run_id, agent_id=agent_id)
        await engine.dispose()
