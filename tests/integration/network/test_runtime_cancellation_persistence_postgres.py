from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkModel,
    NetworkSessionModel,
)
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_cancelled_network_run_persists_user_turn_partial_output_and_terminal_event() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    network_id = uuid4()
    network_session_id = uuid4()
    execution_id = uuid4()
    trace_id = uuid4()

    try:
        async with session_factory() as session:
            async with session.begin():
                session.add(
                    NetworkModel(
                        id=network_id,
                        project_id=project_id,
                        name=f"cancel-persistence-{network_id}",
                        description="",
                        draft_definition={"nodes": [], "edges": []},
                        draft_revision=1,
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
                        title="cancel persistence",
                        status="active",
                    )
                )
            async with session.begin():
                session.add(
                    NetworkExecutionModel(
                        id=execution_id,
                        network_id=network_id,
                        network_version_id=None,
                        network_session_id=network_session_id,
                        project_id=project_id,
                        input_message="persist this network request",
                        draft_revision=1,
                        definition_snapshot={"nodes": [], "edges": []},
                        resolved_bindings_snapshot={},
                        status="running",
                        last_event_sequence=0,
                    )
                )
                session.add(
                    NetworkMessageModel(
                        network_session_id=network_session_id,
                        network_execution_id=execution_id,
                        project_id=project_id,
                        role="user",
                        content="persist this network request",
                    )
                )

        finalizer = NetworkRuntimeFinalizer(session_factory)
        persisted = await finalizer.finalize(
            execution_id=execution_id,
            version=None,
            invocation_states=[],
            terminal_status="cancelled",
            output="partial network answer",
            trace_id=trace_id,
            streamed_output=True,
        )

        assert persisted is True

        async with session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            messages = list(
                (
                    await session.scalars(
                        select(NetworkMessageModel)
                        .where(NetworkMessageModel.network_execution_id == execution_id)
                        .order_by(NetworkMessageModel.created_at.asc())
                    )
                ).all()
            )
            events = list(
                (
                    await session.scalars(
                        select(NetworkExecutionEventModel)
                        .where(NetworkExecutionEventModel.network_execution_id == execution_id)
                        .order_by(NetworkExecutionEventModel.sequence.asc())
                    )
                ).all()
            )

        assert execution is not None
        assert execution.status == "cancelled"
        assert execution.output_message == "partial network answer"
        assert execution.root_trace_id == trace_id
        assert execution.completed_at is not None

        assert [(message.role, message.content) for message in messages] == [
            ("user", "persist this network request"),
            ("assistant", "partial network answer"),
        ]
        assert messages[1].data["cancelled"] is True
        assert messages[1].data["partial"] is True
        assert messages[1].data["trace_id"] == str(trace_id)

        assert [event.event_type for event in events] == ["execution_cancelled"]
        assert events[0].payload["output"] == "partial network answer"
        assert events[0].payload["partial"] is True
        assert events[0].payload["cancelled"] is True
    finally:
        await engine.dispose()
