from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from modules.agent.infra.database.models import AgentModel, MessageModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkInvocationModel,
    NetworkMessageModel,
    NetworkModel,
    NetworkSessionModel,
)
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_network_cancellation_before_first_child_token_does_not_persist_empty_assistant_message() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    network_id = uuid4()
    network_session_id = uuid4()
    execution_id = uuid4()
    agent_id = uuid4()
    node_id = uuid4()
    invocation_id = uuid4()
    agent_session_id = uuid4()
    trace_id = uuid4()
    started_at = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)

    try:
        async with session_factory() as session:
            async with session.begin():
                session.add_all(
                    [
                        AgentModel(
                            id=agent_id,
                            project_id=project_id,
                            provider_credential_id=None,
                            fallback_credential_id=None,
                            name="cancel-before-first-token",
                            description="",
                            type="assistant",
                            system_prompt="",
                            provider="openai",
                            model="test",
                            fallback_provider=None,
                            fallback_model=None,
                            temperature=0.2,
                            max_output_tokens=128,
                            session_mode="stateful",
                            status="active",
                            settings={},
                        ),
                        NetworkModel(
                            id=network_id,
                            project_id=project_id,
                            name=f"cancel-before-token-{network_id}",
                            description="",
                            draft_definition={"nodes": [], "edges": []},
                            draft_revision=1,
                            staging_version_id=None,
                            production_version_id=None,
                        ),
                    ]
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
                        title="cancel before child first token",
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
                        input_message="root request",
                        draft_revision=1,
                        definition_snapshot={"nodes": [], "edges": []},
                        resolved_bindings_snapshot={
                            str(node_id): {
                                "release_id": None,
                                "session_mode": "stateful",
                            }
                        },
                        status="running",
                        last_event_sequence=0,
                    )
                )

        finalizer = NetworkRuntimeFinalizer(session_factory)
        persisted = await finalizer.finalize(
            execution_id=execution_id,
            version=None,
            invocation_states=[
                {
                    "id": str(invocation_id),
                    "agent_id": str(agent_id),
                    "node_id": str(node_id),
                    "parent_invocation_id": None,
                    "agent_session_id": str(agent_session_id),
                    "trace_id": str(trace_id),
                    "depth": 0,
                    "status": "running",
                    "input_message": "root request",
                    "output_message": "",
                    "provider": "openai",
                    "model": "test",
                    "usage": None,
                    "diagnostics": {
                        "schema_version": 5,
                        "usage_complete": False,
                        "cost_status": "unknown",
                    },
                    "llm_calls": [],
                    "tool_calls": [],
                    "sources": [],
                    "started_at": started_at.isoformat(),
                    "persist_context": False,
                }
            ],
            terminal_status="cancelled",
            output="",
            trace_id=trace_id,
            streamed_output=True,
        )

        assert persisted is True

        async with session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            run = await session.get(AgentRunModel, invocation_id)
            invocation = await session.get(NetworkInvocationModel, invocation_id)
            agent_messages = list(
                (
                    await session.scalars(
                        select(MessageModel)
                        .where(MessageModel.session_id == agent_session_id)
                        .order_by(MessageModel.created_at.asc())
                    )
                ).all()
            )
            network_messages = list(
                (
                    await session.scalars(
                        select(NetworkMessageModel).where(
                            NetworkMessageModel.network_execution_id == execution_id,
                            NetworkMessageModel.role == "assistant",
                        )
                    )
                ).all()
            )

        assert execution is not None
        assert execution.status == "cancelled"
        assert execution.output_message == ""
        assert network_messages == []

        assert run is not None
        assert run.status == "cancelled"
        assert run.result["answer"] == ""
        assert run.result["cancelled"] is True
        assert run.result["partial"] is False
        assert run.input_message_id is not None
        assert run.output_message_id is None
        assert run.failure_code is None
        assert run.failure_detail is None

        assert invocation is not None
        assert invocation.status == "cancelled"
        assert invocation.output_message == ""

        assert [(message.role, message.content) for message in agent_messages] == [
            ("user", "root request"),
        ]
        assert run.input_message_id == agent_messages[0].id
    finally:
        await engine.dispose()
