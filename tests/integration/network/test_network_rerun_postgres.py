from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from modules.network.application.rerun_service import NetworkRerunService
from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkModel,
    NetworkOutboxEventModel,
    NetworkSessionModel,
)
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_network_rerun_creates_new_run_from_frozen_snapshot_with_lineage() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    network_id = uuid4()
    network_session_id = uuid4()
    source_execution_id = uuid4()
    node_id = uuid4()
    agent_id = uuid4()
    definition = {
        "nodes": [{"id": str(node_id), "agent_id": str(agent_id)}],
        "edges": [],
        "entry_node_id": str(node_id),
    }
    bindings = {
        str(node_id): {
            "release_id": None,
            "release_version": "draft",
            "session_mode": "stateful",
        }
    }

    async with session_factory() as session:
        async with session.begin():
            session.add(
                NetworkModel(
                    id=network_id,
                    project_id=project_id,
                    name=f"rerun-{network_id}",
                    description="",
                    draft_definition=definition,
                    draft_revision=7,
                    staging_version_id=None,
                    production_version_id=None,
                )
            )
        async with session.begin():
            session.add(
                NetworkSessionModel(
                    id=network_session_id,
                    network_id=network_id,
                    network_version_id=None,
                    project_id=project_id,
                    origin="runtime_api",
                    environment="draft",
                    title="rerun session",
                    status="active",
                )
            )
        async with session.begin():
            session.add(
                NetworkExecutionModel(
                    id=source_execution_id,
                    network_id=network_id,
                    network_version_id=None,
                    network_session_id=network_session_id,
                    project_id=project_id,
                    input_message="original network input",
                    draft_revision=7,
                    definition_snapshot=definition,
                    resolved_bindings_snapshot=bindings,
                    output_message="original output",
                    status="completed",
                    last_event_sequence=3,
                )
            )

    service = NetworkRerunService(session_factory)
    rerun = await service.execute(
        execution_id=source_execution_id,
        project_id=project_id,
        idempotency_key="rerun-key-1",
    )
    second = await service.execute(
        execution_id=source_execution_id,
        project_id=project_id,
        idempotency_key="rerun-key-1",
    )

    assert rerun.id != source_execution_id
    assert second.id == rerun.id
    assert rerun.status == "queued"
    assert rerun.network_session_id == network_session_id
    assert rerun.input_message == "original network input"
    assert rerun.draft_revision == 7
    assert rerun.definition_snapshot == definition
    assert rerun.resolved_bindings_snapshot == bindings
    assert rerun.definition_snapshot is not definition
    assert rerun.resolved_bindings_snapshot is not bindings

    async with session_factory() as session:
        message = await session.scalar(
            select(NetworkMessageModel).where(
                NetworkMessageModel.network_execution_id == rerun.id
            )
        )
        event = await session.scalar(
            select(NetworkExecutionEventModel).where(
                NetworkExecutionEventModel.network_execution_id == rerun.id,
                NetworkExecutionEventModel.sequence == 1,
            )
        )
        outbox = await session.scalar(
            select(NetworkOutboxEventModel).where(
                NetworkOutboxEventModel.aggregate_id == rerun.id
            )
        )

    assert message is not None
    assert message.role == "user"
    assert message.content == "original network input"
    assert message.data["rerun_of_execution_id"] == str(source_execution_id)
    assert event is not None
    assert event.event_type == "execution_accepted"
    assert event.payload["rerun_of_execution_id"] == str(source_execution_id)
    assert outbox is not None
    assert outbox.payload["rerun_of_execution_id"] == str(source_execution_id)
    assert outbox.causation_id == source_execution_id

    await engine.dispose()
