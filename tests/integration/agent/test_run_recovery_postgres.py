from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from modules.agent.infra.database.models import AgentModel, AgentOutboxEventModel
from modules.agent.infra.database.run_models import AgentRunModel
from woobe_workers.consumers.agent.run_recovery_worker import AgentRunRecoveryWorker
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


class _MissingHotState:
    async def get(self, _run_id):
        return None


class _UnavailableHotState:
    async def get(self, _run_id):
        raise RuntimeError("redis unavailable")


async def _seed(session_factory, *, project_id, agent_id, run_id, trace_id) -> None:
    started_at = datetime.now(timezone.utc) - timedelta(minutes=5)
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
            await session.execute(delete(AgentModel).where(AgentModel.id == agent_id))


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
