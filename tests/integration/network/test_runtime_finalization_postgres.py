from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session as SyncSession

from modules.agent.infra.database.models import AgentModel, MessageModel, SessionModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkInvocationModel,
    NetworkModel,
    NetworkSessionModel,
)
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_network_bulk_finalizer_materializes_children_in_one_commit() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    network_id = uuid4()
    network_session_id = uuid4()
    execution_id = uuid4()
    root_agent_id = uuid4()
    child_agent_id = uuid4()
    root_node_id = uuid4()
    child_node_id = uuid4()
    root_invocation_id = uuid4()
    child_invocation_id = uuid4()
    root_agent_session_id = uuid4()
    child_agent_session_id = uuid4()
    root_trace_id = uuid4()
    child_trace_id = uuid4()
    root_started_at = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    child_started_at = root_started_at + timedelta(milliseconds=150)
    child_completed_at = root_started_at + timedelta(milliseconds=550)
    root_completed_at = root_started_at + timedelta(milliseconds=900)

    async with session_factory() as session:
        async with session.begin():
            session.add_all(
                [
                    AgentModel(
                        id=root_agent_id,
                        project_id=project_id,
                        provider_credential_id=None,
                        fallback_credential_id=None,
                        name="root-agent",
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
                    AgentModel(
                        id=child_agent_id,
                        project_id=project_id,
                        provider_credential_id=None,
                        fallback_credential_id=None,
                        name="child-agent",
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
                        name=f"bulk-finalizer-{network_id}",
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
                    title="bulk finalizer session",
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
                    input_message="root input",
                    draft_revision=1,
                    definition_snapshot={"nodes": [], "edges": []},
                    resolved_bindings_snapshot={
                        str(root_node_id): {
                            "release_id": None,
                            "session_mode": "stateful",
                        },
                        str(child_node_id): {
                            "release_id": None,
                            "session_mode": "stateful",
                        },
                    },
                    status="queued",
                    last_event_sequence=0,
                )
            )

    commits = 0

    def after_commit(_session) -> None:
        nonlocal commits
        commits += 1

    event.listen(SyncSession, "after_commit", after_commit)
    try:
        finalizer = NetworkRuntimeFinalizer(session_factory)
        persisted = await finalizer.finalize(
            execution_id=execution_id,
            version=None,
            invocation_states=[
                {
                    "id": str(root_invocation_id),
                    "agent_id": str(root_agent_id),
                    "node_id": str(root_node_id),
                    "parent_invocation_id": None,
                    "agent_session_id": str(root_agent_session_id),
                    "trace_id": str(root_trace_id),
                    "depth": 0,
                    "status": "completed",
                    "input_message": "root input",
                    "output_message": "root output",
                    "provider": "openai",
                    "model": "test",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                        "cost_usd": 0.01,
                    },
                    "diagnostics": {
                        "schema_version": 5,
                        "llm_work_latency_ms": 500,
                        "tool_work_latency_ms": 0,
                        "usage_complete": True,
                        "cost_status": "known",
                        "cost_usd": 0.01,
                    },
                    "llm_calls": [
                        {
                            "call_id": "root-llm",
                            "latency_ms": 500,
                            "cost_status": "known",
                        }
                    ],
                    "tool_calls": [],
                    "sources": [],
                    "started_at": root_started_at.isoformat(),
                    "completed_at": root_completed_at.isoformat(),
                    "persist_context": True,
                },
                {
                    "id": str(child_invocation_id),
                    "agent_id": str(child_agent_id),
                    "node_id": str(child_node_id),
                    "parent_invocation_id": str(root_invocation_id),
                    "agent_session_id": str(child_agent_session_id),
                    "trace_id": str(child_trace_id),
                    "depth": 1,
                    "status": "completed",
                    "input_message": "delegated input",
                    "output_message": "child output",
                    "provider": "openai",
                    "model": "test",
                    "usage": {
                        "input_tokens": 4,
                        "output_tokens": 3,
                        "total_tokens": 7,
                        "cost_usd": 0.002,
                    },
                    "diagnostics": {
                        "schema_version": 5,
                        "llm_work_latency_ms": 250,
                        "tool_work_latency_ms": 25,
                        "usage_complete": True,
                        "cost_status": "known",
                        "cost_usd": 0.002,
                    },
                    "llm_calls": [
                        {
                            "call_id": "child-llm",
                            "latency_ms": 250,
                            "cost_status": "known",
                        }
                    ],
                    "tool_calls": [
                        {
                            "tool_name": "lookup",
                            "duration_ms": 25,
                            "success": True,
                        }
                    ],
                    "sources": [],
                    "started_at": child_started_at.isoformat(),
                    "completed_at": child_completed_at.isoformat(),
                    "persist_context": True,
                },
            ],
            terminal_status="completed",
            output="root output",
            trace_id=root_trace_id,
            streamed_output=True,
        )
    finally:
        event.remove(SyncSession, "after_commit", after_commit)

    assert persisted is True
    assert commits == 1, "Network bulk finalization must be one PostgreSQL commit"

    async with session_factory() as session:
        execution = await session.get(NetworkExecutionModel, execution_id)
        invocations = list(
            (
                await session.scalars(
                    select(NetworkInvocationModel).where(
                        NetworkInvocationModel.network_execution_id == execution_id
                    )
                )
            ).all()
        )
        runs = list(
            (
                await session.scalars(
                    select(AgentRunModel).where(
                        AgentRunModel.network_execution_id == execution_id
                    )
                )
            ).all()
        )
        execution_events = list(
            (
                await session.scalars(
                    select(NetworkExecutionEventModel)
                    .where(NetworkExecutionEventModel.network_execution_id == execution_id)
                    .order_by(NetworkExecutionEventModel.sequence.asc())
                )
            ).all()
        )
        agent_sessions = list(
            (
                await session.scalars(
                    select(SessionModel).where(
                        SessionModel.id.in_([root_agent_session_id, child_agent_session_id])
                    )
                )
            ).all()
        )
        messages = list(
            (
                await session.scalars(
                    select(MessageModel).where(
                        MessageModel.session_id.in_([root_agent_session_id, child_agent_session_id])
                    )
                )
            ).all()
        )
        contexts = list(
            (
                await session.scalars(
                    select(NetworkAgentContextModel).where(
                        NetworkAgentContextModel.network_session_id == network_session_id
                    )
                )
            ).all()
        )

    assert execution is not None
    assert execution.status == "completed"
    assert execution.output_message == "root output"
    assert {item.id for item in invocations} == {
        root_invocation_id,
        child_invocation_id,
    }
    child_invocation = next(item for item in invocations if item.id == child_invocation_id)
    assert child_invocation.parent_invocation_id == root_invocation_id
    assert {item.id for item in runs} == {root_invocation_id, child_invocation_id}
    child_run = next(item for item in runs if item.id == child_invocation_id)
    assert child_run.parent_run_id == root_invocation_id
    assert child_run.usage["total_tokens"] == 7
    assert child_run.result["diagnostics"]["schema_version"] == 5
    assert child_run.result["diagnostics"]["llm_work_latency_ms"] == 250
    assert child_run.result["llm_calls"][0]["call_id"] == "child-llm"
    assert child_run.started_at == child_started_at
    assert child_run.completed_at == child_completed_at

    completed_events = [
        item
        for item in execution_events
        if item.event_type == "agent_invocation_completed"
    ]
    assert len(completed_events) == 2
    child_completed_event = next(
        item for item in completed_events if item.invocation_id == child_invocation_id
    )
    assert child_completed_event.payload["usage"]["total_tokens"] == 7
    assert child_completed_event.payload["diagnostics"]["schema_version"] == 5
    assert child_completed_event.payload["tool_calls"][0]["tool_name"] == "lookup"

    assert len(agent_sessions) == 2
    assert len(messages) == 4
    assert {item.network_node_id for item in contexts} == {root_node_id, child_node_id}

    await engine.dispose()
