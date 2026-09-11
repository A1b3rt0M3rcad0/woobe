from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from modules.agent.infra.database.models import AgentModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkModel,
    NetworkSessionModel,
)
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from modules.network.infra.runtime.run_event_projector import NetworkRunEventProjector
from shared.contracts.run_event_journal import DurableRunEvent
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.in_memory_run_event_journal import InMemoryRunEventJournal
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


def _event(*, run_id, sequence: int, event_type: str, payload: dict) -> DurableRunEvent:
    return DurableRunEvent(
        run_id=run_id,
        run_kind="network",
        sequence=sequence,
        event_id=f"event-{sequence}",
        event_type=event_type,
        occurred_at=f"2026-09-11T03:10:0{sequence}+00:00",
        schema_version=1,
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        metadata={"visibility": "internal"},
        payload=payload,
    )


@pytest.mark.asyncio
async def test_network_terminal_journal_projects_agent_run_read_model() -> None:
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
    trace_id = uuid4()
    started_at = datetime(2026, 9, 11, 3, 10, tzinfo=timezone.utc)
    completed_at = datetime(2026, 9, 11, 3, 10, 1, tzinfo=timezone.utc)

    async with session_factory() as session:
        async with session.begin():
            session.add(
                AgentModel(
                    id=agent_id,
                    project_id=project_id,
                    provider_credential_id=None,
                    fallback_credential_id=None,
                    name="journal-agent",
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
            session.add(
                NetworkModel(
                    id=network_id,
                    project_id=project_id,
                    name=f"journal-network-{network_id}",
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
                    title="journal projection",
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
                    input_message="hello",
                    draft_revision=1,
                    definition_snapshot={"nodes": [], "edges": []},
                    resolved_bindings_snapshot={
                        str(node_id): {
                            "release_id": None,
                            "session_mode": "stateless",
                        }
                    },
                    status="running",
                    last_event_sequence=0,
                    storage_version=EVENT_JOURNAL_STORAGE_VERSION,
                    journal_projected_sequence=0,
                )
            )

    events = [
        _event(
            run_id=execution_id,
            sequence=1,
            event_type="run.attempt.started",
            payload={"attempt": 1},
        ),
        _event(
            run_id=execution_id,
            sequence=2,
            event_type="agent.invocation.completed",
            payload={
                "invocation": {
                    "id": str(invocation_id),
                    "agent_run_id": str(invocation_id),
                    "agent_id": str(agent_id),
                    "node_id": str(node_id),
                    "parent_invocation_id": None,
                    "agent_session_id": None,
                    "trace_id": str(trace_id),
                    "depth": 0,
                    "status": "completed",
                    "input_message": "hello",
                    "output_message": "done",
                    "provider": "openai",
                    "model": "test",
                    "usage": {
                        "input_tokens": 3,
                        "output_tokens": 2,
                        "total_tokens": 5,
                        "cost_usd": 0.001,
                    },
                    "diagnostics": {
                        "schema_version": 5,
                        "usage_complete": True,
                        "cost_status": "known",
                    },
                    "llm_calls": [],
                    "tool_calls": [],
                    "sources": [],
                    "persist_context": False,
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                }
            },
        ),
        _event(
            run_id=execution_id,
            sequence=3,
            event_type="run.completed",
            payload={
                "output": "done",
                "trace_id": str(trace_id),
                "streamed_output": True,
            },
        ),
    ]

    journal = InMemoryRunEventJournal()
    await journal.write_batch(events)
    projector = NetworkRunEventProjector(
        session_factory,
        journal=journal,
        finalizer=NetworkRuntimeFinalizer(session_factory),
    )

    await projector.project(events)

    async with session_factory() as session:
        execution = await session.get(NetworkExecutionModel, execution_id)
        agent_run = await session.get(AgentRunModel, invocation_id)

    assert execution is not None
    assert execution.status == "completed"
    assert execution.output_message == "done"
    assert execution.journal_projected_sequence == 3

    assert agent_run is not None
    assert agent_run.id == invocation_id
    assert agent_run.network_execution_id == execution_id
    assert agent_run.network_invocation_id == invocation_id
    assert agent_run.agent_id == agent_id
    assert agent_run.trace_id == trace_id
    assert agent_run.status == "completed"
    assert agent_run.result["answer"] == "done"
    assert agent_run.usage["total_tokens"] == 5

    await engine.dispose()
