from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from modules.agent.infra.database.context_models import (
    ContextSnapshotModel,
    ModelInvocationModel,
)
from modules.agent.infra.database.models import AgentModel, MessageModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkInvocationModel,
    NetworkModel,
    NetworkSessionModel,
)
from modules.network.infra.database.run_diagnostics_reader import NetworkRunDiagnosticsReader
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_network_cancellation_materializes_running_root_agent_as_cancelled_with_partial_output() -> None:
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
    model_invocation_id = uuid4()
    context_snapshot_id = uuid4()
    started_at = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
    completed_at = started_at + timedelta(seconds=6.4)
    context_snapshot = {
        "id": str(context_snapshot_id),
        "policy_schema_version": 1,
        "policy_hash": "network-cancel-policy",
        "model_capacity_units": 128000,
        "reserved_output_units": 2048,
        "runtime_reserve_units": 0,
        "usable_input_budget": 125952,
        "estimated_input_units": 512,
        "reported_input_units": 512,
        "utilization": 0.004,
        "pressure_status": "LOW",
        "measurement_status": "reported",
        "manifest": {},
        "materialized_hash": "network-cancel-context",
        "retention_mode": "references_only",
        "reproduction_level": "manifest_only",
        "contributions": [],
    }
    cancelled_llm_call = {
        "call_id": str(model_invocation_id),
        "call_index": 1,
        "phase": "capability_response_generation",
        "status": "cancelled",
        "error": None,
        "started_at": started_at.isoformat(),
        "ended_at": completed_at.isoformat(),
        "occurred_at": completed_at.isoformat(),
        "latency_ms": 6100,
        "input_tokens": 512,
        "output_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
        "cost_status": "unknown_tokens",
        "cost_reason": "Model invocation was cancelled before final provider usage",
        "usage_complete": False,
        "provider": "openai",
        "model": "test",
        "context_snapshot": context_snapshot,
        "provider_model_id": None,
        "provider_credential_id": None,
        "pricing_id": None,
        "pricing_snapshot": None,
    }

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
                            name="cancelled-root",
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
                            name=f"cancelled-child-{network_id}",
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
                        title="cancel child persistence",
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
                    "output_message": "partial root answer",
                    "provider": "openai",
                    "model": "test",
                    "usage": {
                        "input_tokens": 512,
                        "output_tokens": None,
                        "total_tokens": None,
                        "cost_usd": None,
                    },
                    "diagnostics": {
                        "schema_version": 5,
                        "agent_runtime_latency_ms": 6400,
                        "total_latency_ms": 6400,
                        "prepare_latency_ms": 100,
                        "llm_work_latency_ms": 6100,
                        "llm_runtime_latency_ms": 6100,
                        "tool_wall_latency_ms": 0,
                        "tool_work_latency_ms": 0,
                        "tool_call_duration_sum_ms": 0,
                        "finalization_work_latency_ms": 0,
                        "persistence_latency_ms": 0,
                        "other_latency_ms": 200,
                        "unaccounted_latency_ms": 200,
                        "orchestration_latency_ms": None,
                        "llm_call_count": 1,
                        "tool_call_count": 0,
                        "usage_complete": False,
                        "cost_status": "unknown_tokens",
                    },
                    "llm_calls": [cancelled_llm_call],
                    "tool_calls": [],
                    "sources": [],
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                    "persist_context": False,
                }
            ],
            terminal_status="cancelled",
            output="partial root answer",
            trace_id=trace_id,
            streamed_output=True,
        )

        assert persisted is True

        async with session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            run = await session.get(AgentRunModel, invocation_id)
            invocation = await session.get(NetworkInvocationModel, invocation_id)
            model_invocation = await session.get(ModelInvocationModel, model_invocation_id)
            context_evidence = await session.get(ContextSnapshotModel, context_snapshot_id)
            diagnostics = await NetworkRunDiagnosticsReader(session).get(
                execution_id,
                project_id,
            )
            messages = list(
                (
                    await session.scalars(
                        select(MessageModel)
                        .where(MessageModel.session_id == agent_session_id)
                        .order_by(MessageModel.created_at.asc())
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
        assert execution.output_message == "partial root answer"

        assert run is not None
        assert str(run.status) == "cancelled"
        assert run.result["answer"] == "partial root answer"
        assert run.result["cancelled"] is True
        assert run.result["partial"] is True
        assert run.result["diagnostics"]["llm_call_count"] == 1
        assert run.result["diagnostics"]["llm_work_latency_ms"] == 6100
        assert run.result["diagnostics"]["usage_complete"] is False
        assert run.result["llm_calls"][0]["status"] == "cancelled"
        assert run.usage["input_tokens"] == 512
        assert run.failure_code is None
        assert run.failure_detail is None
        assert run.completed_at is not None

        assert model_invocation is not None
        assert model_invocation.agent_run_id == invocation_id
        assert model_invocation.status == "cancelled"
        assert model_invocation.phase == "capability_response_generation"
        assert model_invocation.latency_ms == 6100
        assert model_invocation.input_units == 512
        assert model_invocation.output_units is None

        assert context_evidence is not None
        assert context_evidence.agent_run_id == invocation_id
        assert context_evidence.model_invocation_id == model_invocation_id
        assert context_evidence.policy_hash == "network-cancel-policy"
        assert context_evidence.reported_input_units == 512

        assert diagnostics is not None
        assert diagnostics["status"] == "cancelled"
        assert diagnostics["agent_run_count"] == 1
        assert diagnostics["llm_call_count"] == 1
        assert diagnostics["llm_runtime_latency_ms"] == 6100
        assert diagnostics["input_tokens"] == 512
        assert diagnostics["usage_complete"] is False
        assert diagnostics["context"]["model_invocation_count"] == 1
        assert diagnostics["context"]["telemetry_status"] == "complete"

        assert invocation is not None
        assert invocation.status == "cancelled"
        assert invocation.output_message == "partial root answer"

        assert [(message.role, message.content) for message in messages] == [
            ("user", "root request"),
            ("assistant", "partial root answer"),
        ]
        assert run.input_message_id == messages[0].id
        assert run.output_message_id == messages[1].id
        assert messages[1].data["cancelled"] is True
        assert messages[1].data["partial"] is True

        # Finalization is one PostgreSQL transaction: child Run evidence is ordered
        # before the Network terminal event, so a durable reader never sees an
        # execution_cancelled event without the cancelled AgentRun it summarizes.
        assert [event.event_type for event in events] == [
            "agent_invocation_started",
            "agent_invocation_cancelled",
            "execution_cancelled",
        ]
        assert [event.sequence for event in events] == [1, 2, 3]
        assert events[1].invocation_id == invocation_id
        assert events[2].invocation_id is None
    finally:
        await engine.dispose()
