from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.domain.run import AgentRun
from modules.agent.infra.execution.agent_run_reattach_service import AgentRunReattachService
from shared.contracts.run_event_journal import DurableRunEvent, RunJournalState
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.infra.in_memory_run_event_journal import InMemoryRunEventJournal
from shared.runtime import RunReference, RuntimeEventPublisher, RuntimeObserver, RuntimeStreamReader
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION
from shared.security.principal import ProjectApiPrincipal


class _Runs:
    def __init__(self, run: AgentRun) -> None:
        self.run = run

    async def get_active_direct_by_session(self, session_id):
        return self.run if self.run.session_id == session_id else None


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        self.repositories = SimpleNamespace(
            runs=_Runs(run),
            project_access=SimpleNamespace(),
        )

    async def read(self, operation):
        return await operation(self.repositories, None)


class _TerminalJournal:
    def __init__(self, run_id) -> None:
        self.run_id = run_id

    async def get_state(self, run_id):
        if run_id != self.run_id:
            return None
        return RunJournalState(
            run_id=run_id,
            run_kind="agent",
            storage_version=EVENT_JOURNAL_STORAGE_VERSION,
            durable_sequence=4,
            terminal_sequence=4,
            terminal_status="completed",
        )


def _direct_run() -> AgentRun:
    return AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        trace_id=uuid4(),
        environment="production",
        origin="runtime_api",
        input_message="hello",
        execution_snapshot={},
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
    )


def _principal(run: AgentRun) -> ProjectApiPrincipal:
    return ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=run.project_id,
        key_prefix="rai_live_test",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        target_type="agent",
        target_id=run.agent_id,
        agent_id=run.agent_id,
        environment=run.environment,
        interfaces=frozenset({"http", "stream"}),
        authenticated_at=datetime.now(UTC),
    )


def _journal_event(*, run_id, sequence: int, event_type: str, payload: dict) -> DurableRunEvent:
    return DurableRunEvent(
        run_id=run_id,
        run_kind="network",
        sequence=sequence,
        event_id=f"event-{sequence}",
        event_type=event_type,
        occurred_at=f"2026-09-10T20:00:0{sequence}+00:00",
        schema_version=1,
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        metadata={"visibility": "internal"},
        payload=payload,
    )


@pytest.mark.asyncio
async def test_active_agent_run_does_not_return_sql_running_after_durable_terminal() -> None:
    run = _direct_run()
    service = AgentRunReattachService(
        transactions=_Transactions(run),
        state_store=InMemoryExecutionStateStore(),
        journal=_TerminalJournal(run.id),
    )

    active = await service.active(
        session_id=run.session_id,
        principal=_principal(run),
    )

    assert active is None


@pytest.mark.asyncio
async def test_hot_network_projection_preserves_agent_run_identity() -> None:
    store = InMemoryExecutionStateStore()
    publisher = RuntimeEventPublisher(store, projection_interval_seconds=0)
    execution_id = uuid4()
    invocation_id = uuid4()
    agent_run_id = uuid4()
    await store.create(execution_id, {"status": "running"}, ttl_seconds=3600)

    await publisher.publish(
        execution_id,
        "network",
        "agent_invocation_started",
        {
            "invocation_id": str(invocation_id),
            "agent_run_id": str(agent_run_id),
            "node_id": str(uuid4()),
            "agent_id": str(uuid4()),
            "depth": 0,
            "label": "Billing Agent",
        },
    )

    projection, _ = await RuntimeStreamReader(store).current_state(
        execution_id,
        "network",
        durable_fallback=lambda: None,
    )

    assert projection is not None
    assert projection["invocations"][0]["agent_run_id"] == str(agent_run_id)


@pytest.mark.asyncio
async def test_durable_network_projection_preserves_agent_run_identity() -> None:
    execution_id = uuid4()
    invocation_id = uuid4()
    agent_run_id = uuid4()
    journal = InMemoryRunEventJournal()
    await journal.write_batch(
        [
            _journal_event(
                run_id=execution_id,
                sequence=1,
                event_type="run.attempt.started",
                payload={},
            ),
            _journal_event(
                run_id=execution_id,
                sequence=2,
                event_type="agent.invocation.started",
                payload={
                    "invocation": {
                        "id": str(invocation_id),
                        "agent_run_id": str(agent_run_id),
                        "agent_id": str(uuid4()),
                        "node_id": str(uuid4()),
                        "depth": 0,
                        "label": "Billing Agent",
                        "status": "running",
                    }
                },
            ),
            _journal_event(
                run_id=execution_id,
                sequence=3,
                event_type="run.completed",
                payload={"output": "done"},
            ),
        ]
    )
    observer = RuntimeObserver(
        InMemoryExecutionStateStore(),
        journal=journal,
        local_poll_seconds=0.01,
    )

    async def relational_fallback():
        return {"status": "running", "output": ""}

    stream = observer.observe(
        RunReference.network(execution_id),
        durable_fallback=relational_fallback,
    )
    frame = await anext(stream)

    assert frame.event_type == "run.state"
    assert frame.data["invocations"][0]["agent_run_id"] == str(agent_run_id)
    await stream.aclose()
