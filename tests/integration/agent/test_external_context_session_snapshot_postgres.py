from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from modules.agent.domain.entities import Session
from modules.agent.infra.database.models import AgentModel, SessionModel
from modules.agent.infra.database.runtime_session_repository import (
    SQLAlchemyRuntimeSessionRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.core.infra.database.models import ProjectModel
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


async def _seed_session():
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    async with session_factory() as db, db.begin():
        db.add(
            ProjectModel(
                id=project_id,
                workspace_id=uuid4(),
                name="External Context Session test",
                slug=f"external-context-{project_id}",
                status="active",
                data={},
            )
        )
        await db.flush()
        db.add(
            AgentModel(
                id=agent_id,
                project_id=project_id,
                provider_credential_id=None,
                fallback_credential_id=None,
                name="External Context Session Agent",
                description="",
                type="assistant",
                system_prompt="",
                provider="openai",
                model="test-model",
                fallback_provider=None,
                fallback_model=None,
                temperature=0.0,
                max_output_tokens=32,
                session_mode="stateful",
                status="active",
                settings={},
            )
        )
        await db.flush()
        db.add(
            SessionModel(
                id=session_id,
                project_id=project_id,
                agent_id=agent_id,
                runtime_environment="draft",
                opened_release_id=None,
                external_session_id=None,
                tenant_id=None,
                user_id=None,
                status="active",
                mode="chat",
                data=None,
                external_context_snapshot=None,
                last_message_at=None,
            )
        )

    return engine, session_factory, project_id, agent_id, session_id


@pytest.mark.asyncio
async def test_runtime_session_external_context_snapshot_survives_new_connection() -> None:
    engine, session_factory, _project_id, _agent_id, session_id = await _seed_session()

    async with AgentUnitOfWork(engine) as uow:
        repo = SQLAlchemyRuntimeSessionRepository(uow)
        entity = await repo.get_by_id_for_update(session_id)
        entity.external_context_snapshot = {"client_id": "client-123"}
        await repo.update(entity)

    async with session_factory() as db:
        persisted = await db.get(SessionModel, session_id)

    assert persisted is not None
    assert persisted.external_context_snapshot == {"client_id": "client-123"}
    await engine.dispose()


@pytest.mark.asyncio
async def test_runtime_session_row_lock_serializes_first_session_field_initialization() -> None:
    engine, _session_factory, _project_id, _agent_id, session_id = await _seed_session()
    first_locked = asyncio.Event()
    release_first = asyncio.Event()
    second_acquired = asyncio.Event()
    second_snapshot = None

    async def first_writer() -> None:
        async with AgentUnitOfWork(engine) as uow:
            repo = SQLAlchemyRuntimeSessionRepository(uow)
            entity = await repo.get_by_id_for_update(session_id)
            first_locked.set()
            await release_first.wait()
            entity.external_context_snapshot = {"client_id": "client-123"}
            await repo.update(entity)

    async def second_writer() -> None:
        nonlocal second_snapshot
        await first_locked.wait()
        async with AgentUnitOfWork(engine) as uow:
            repo = SQLAlchemyRuntimeSessionRepository(uow)
            entity = await repo.get_by_id_for_update(session_id)
            second_snapshot = entity.external_context_snapshot
            second_acquired.set()

    first_task = asyncio.create_task(first_writer())
    await first_locked.wait()
    second_task = asyncio.create_task(second_writer())

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(second_acquired.wait(), timeout=0.05)

    release_first.set()
    await asyncio.gather(first_task, second_task)

    assert second_snapshot == {"client_id": "client-123"}
    await engine.dispose()
