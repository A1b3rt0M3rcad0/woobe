from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete

from modules.network.application.runtime import NetworkExecutionSnapshot
from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkModel,
    NetworkSessionModel,
)
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from modules.network.infra.runtime.loader import NetworkRuntimeLoader
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from modules.network.infra.workers.execution_worker import NetworkLeaseRecoveryWorker
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.redis_execution_state import RedisExecutionStateStore


@pytest.mark.asyncio
async def test_recovery_worker_persists_terminal_redis_state_after_owner_loss() -> None:
    settings = Settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    redis_url = os.environ.get("WOOBE_REDIS_URL")
    assert redis_url, "integration runtime must provide WOOBE_REDIS_URL"
    redis_client = Redis.from_url(redis_url, decode_responses=True)

    project_id = uuid4()
    network_id = uuid4()
    session_id = uuid4()
    execution_id = uuid4()
    prefix = f"woobe:test:network-recovery:{execution_id}"
    state_store = RedisExecutionStateStore(redis_client, key_prefix=prefix)
    store = RedisNetworkExecutionStore(state_store)
    old = datetime.now(timezone.utc) - timedelta(minutes=2)
    definition = {
        "schema_version": 2,
        "root_node_id": None,
        "nodes": [],
        "edges": [],
        "settings": {
            "session_mode": "stateless",
            "max_depth": 2,
            "max_invocations": 4,
            "timeout_seconds": 30,
        },
    }

    async with session_factory() as session, session.begin():
        session.add(
            NetworkModel(
                id=network_id,
                project_id=project_id,
                name=f"terminal-recovery-{network_id}",
                description="",
                draft_definition=definition,
                draft_revision=1,
                staging_version_id=None,
                production_version_id=None,
            )
        )
        await session.flush()
        session.add(
            NetworkSessionModel(
                id=session_id,
                network_id=network_id,
                network_version_id=None,
                project_id=project_id,
                origin="runtime_api",
                environment="draft",
                title="terminal recovery",
                tenant_id=None,
                user_id=None,
                external_session_id=None,
                status="active",
            )
        )
        await session.flush()
        session.add(
            NetworkExecutionModel(
                id=execution_id,
                network_id=network_id,
                network_version_id=None,
                network_session_id=session_id,
                project_id=project_id,
                input_message="recover me",
                draft_revision=1,
                definition_snapshot=definition,
                resolved_bindings_snapshot={},
                output_message=None,
                status="running",
                idempotency_key=f"terminal-recovery-{execution_id}",
                root_trace_id=None,
                attempt=1,
                lease_owner="dead-worker",
                lease_generation=1,
                lease_expires_at=old,
                heartbeat_at=old,
                cancel_requested_at=None,
                failure_code=None,
                failure_detail=None,
                last_event_sequence=0,
                started_at=old,
                completed_at=None,
                created_at=old,
                updated_at=old,
            )
        )

    snapshot = NetworkExecutionSnapshot(
        id=execution_id,
        network_id=network_id,
        network_version_id=None,
        network_session_id=session_id,
        project_id=project_id,
        input_message="recover me",
        draft_revision=1,
        definition_snapshot=definition,
        resolved_bindings_snapshot={},
        status="running",
    )
    await store.initialize(snapshot, ttl_seconds=3600, agent_contexts={})
    await store.mark_terminal_pending(
        execution_id,
        status="cancelled",
        result={
            "output": "durable partial",
            "trace_id": None,
            "partial": True,
            "cancelled": True,
        },
    )

    worker = NetworkLeaseRecoveryWorker(
        loader=NetworkRuntimeLoader(session_factory),
        store=store,
        finalizer=NetworkRuntimeFinalizer(session_factory),
        lease_ttl_seconds=1,
    )

    state_key = f"{prefix}:run:{execution_id}"
    events_key = f"{state_key}:events"
    lease_key = f"{state_key}:lease"
    try:
        assert await redis_client.ping() is True
        await worker.run()

        async with session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            assert execution is not None
            assert execution.status == "cancelled"
            assert execution.output_message == "durable partial"
            assert execution.completed_at is not None
            assert execution.lease_owner is None

        hot = await store.snapshot(execution_id)
        assert hot["status"] == "cancelled"
        assert hot["terminal_status"] == "cancelled"
    finally:
        await redis_client.delete(state_key, events_key, lease_key)
        await redis_client.aclose()
        async with session_factory() as session, session.begin():
            await session.execute(
                delete(NetworkExecutionEventModel).where(
                    NetworkExecutionEventModel.network_execution_id == execution_id
                )
            )
            await session.execute(
                delete(NetworkMessageModel).where(
                    NetworkMessageModel.network_execution_id == execution_id
                )
            )
            await session.execute(
                delete(NetworkExecutionModel).where(NetworkExecutionModel.id == execution_id)
            )
            await session.execute(
                delete(NetworkSessionModel).where(NetworkSessionModel.id == session_id)
            )
            await session.execute(delete(NetworkModel).where(NetworkModel.id == network_id))
        await engine.dispose()
