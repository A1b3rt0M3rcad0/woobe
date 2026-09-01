from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session as SyncSession

from modules.agent.infra.database.context_models import (
    ContextContributionModel,
    ContextSnapshotModel,
    ModelInvocationModel,
)
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


def _context_snapshot(
    *,
    snapshot_id: UUID,
    contribution_id: UUID,
    invocation_id: UUID,
    agent_run_id: UUID,
    source_type: str,
    source_ref: str,
    input_units: int,
) -> dict:
    return {
        "id": str(snapshot_id),
        "project_id": str(uuid4()),
        "model_invocation_id": str(invocation_id),
        "agent_run_id": str(agent_run_id),
        "policy_schema_version": 1,
        "policy_hash": "a" * 64,
        "model_capacity_units": 128000,
        "reserved_output_units": 128,
        "runtime_reserve_units": 0,
        "usable_input_budget": 127872,
        "estimated_input_units": input_units,
        "reported_input_units": input_units,
        "utilization": input_units / 127872,
        "pressure_status": "LOW",
        "measurement_status": "reported",
        "manifest": {
            "schema_version": 1,
            "model_invocation_id": str(invocation_id),
            "agent_run_id": str(agent_run_id),
            "sources": {source_type: {"count": 1, "units": input_units}},
        },
        "materialized_hash": "b" * 64,
        "retention_mode": "references_only",
        "reproduction_level": "manifest_only",
        "contributions": [
            {
                "id": str(contribution_id),
                "ordinal": 0,
                "source_type": source_type,
                "source_ref": source_ref,
                "parent_ref": None,
                "modality": "text",
                "priority": "HIGH" if source_type == "DELEGATION" else "MANDATORY",
                "raw_units": input_units,
                "materialized_units": input_units,
                "selection_method": "runtime_materialization",
                "relevance_score": None,
                "transformations": [],
                "trust": "internal",
                "sensitivity": "internal",
                "integrity_hash": "c" * 64,
                "metadata": {},
            }
        ],
    }


def _llm_call(
    *,
    call_id: UUID,
    run_id: UUID,
    snapshot_id: UUID,
    contribution_id: UUID,
    source_type: str,
    source_ref: str,
    started_at: datetime,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> dict:
    ended_at = started_at + timedelta(milliseconds=latency_ms)
    return {
        "call_id": str(call_id),
        "call_index": 1,
        "phase": "response_generation",
        "status": "success",
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "occurred_at": ended_at.isoformat(),
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": cost_usd,
        "cost_status": "known",
        "usage_complete": True,
        "provider": "openai",
        "model": "test",
        "context_snapshot": _context_snapshot(
            snapshot_id=snapshot_id,
            contribution_id=contribution_id,
            invocation_id=call_id,
            agent_run_id=run_id,
            source_type=source_type,
            source_ref=source_ref,
            input_units=input_tokens,
        ),
    }


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
    root_model_invocation_id = uuid4()
    child_model_invocation_id = uuid4()
    root_context_snapshot_id = uuid4()
    child_context_snapshot_id = uuid4()
    root_contribution_id = uuid4()
    child_contribution_id = uuid4()
    root_started_at = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    child_started_at = root_started_at + timedelta(milliseconds=150)
    child_completed_at = root_started_at + timedelta(milliseconds=550)
    root_completed_at = root_started_at + timedelta(milliseconds=900)

    root_llm_call = _llm_call(
        call_id=root_model_invocation_id,
        run_id=root_invocation_id,
        snapshot_id=root_context_snapshot_id,
        contribution_id=root_contribution_id,
        source_type="USER_INPUT",
        source_ref=str(root_invocation_id),
        started_at=root_started_at,
        latency_ms=500,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.01,
    )
    child_llm_call = _llm_call(
        call_id=child_model_invocation_id,
        run_id=child_invocation_id,
        snapshot_id=child_context_snapshot_id,
        contribution_id=child_contribution_id,
        source_type="DELEGATION",
        source_ref=str(root_invocation_id),
        started_at=child_started_at,
        latency_ms=250,
        input_tokens=4,
        output_tokens=3,
        cost_usd=0.002,
    )

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
                    "llm_calls": [root_llm_call],
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
                    "llm_calls": [child_llm_call],
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
        model_invocations = list(
            (
                await session.scalars(
                    select(ModelInvocationModel).where(
                        ModelInvocationModel.network_execution_id == execution_id
                    )
                )
            ).all()
        )
        context_snapshots = list(
            (
                await session.scalars(
                    select(ContextSnapshotModel).where(
                        ContextSnapshotModel.agent_run_id.in_(
                            [root_invocation_id, child_invocation_id]
                        )
                    )
                )
            ).all()
        )
        snapshot_ids = [item.id for item in context_snapshots]
        context_contributions = list(
            (
                await session.scalars(
                    select(ContextContributionModel).where(
                        ContextContributionModel.snapshot_id.in_(snapshot_ids)
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
    assert child_run.result["llm_calls"][0]["call_id"] == str(child_model_invocation_id)
    assert child_run.started_at == child_started_at
    assert child_run.completed_at == child_completed_at

    assert {item.id for item in model_invocations} == {
        root_model_invocation_id,
        child_model_invocation_id,
    }
    child_model_invocation = next(
        item for item in model_invocations if item.id == child_model_invocation_id
    )
    assert child_model_invocation.agent_run_id == child_invocation_id
    assert child_model_invocation.network_execution_id == execution_id
    assert child_model_invocation.network_invocation_id == child_invocation_id
    assert child_model_invocation.trace_id == child_trace_id
    assert child_model_invocation.input_units == 4
    assert {item.id for item in context_snapshots} == {
        root_context_snapshot_id,
        child_context_snapshot_id,
    }
    child_snapshot = next(
        item for item in context_snapshots if item.id == child_context_snapshot_id
    )
    assert child_snapshot.agent_run_id == child_invocation_id
    assert child_snapshot.model_invocation_id == child_model_invocation_id
    child_contribution = next(
        item for item in context_contributions if item.id == child_contribution_id
    )
    assert child_contribution.snapshot_id == child_context_snapshot_id
    assert child_contribution.source_type == "DELEGATION"
    assert child_contribution.source_ref == str(root_invocation_id)

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
