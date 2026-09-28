from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from modules.agent.domain.run import AgentRun
from modules.agent.infra.execution.agent_run_reattach_service import (
    AgentRunReattachService,
)
from modules.network.infra.services.journal_aware_boundary_service import (
    JournalAwareNetworkBoundaryService,
)
from shared.contracts.run_event_journal import DurableRunEvent, RunJournalState
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.infra.in_memory_run_event_journal import InMemoryRunEventJournal
from shared.runtime import (
    RunReference,
    RuntimeEventPublisher,
    RuntimeObserver,
    RuntimeStreamReader,
)
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
    def __init__(self, run_id, run_kind: str = "agent") -> None:
        self.run_id = run_id
        self.run_kind = run_kind

    async def get_state(self, run_id):
        if run_id != self.run_id:
            return None
        return RunJournalState(
            run_id=run_id,
            run_kind=self.run_kind,
            storage_version=EVENT_JOURNAL_STORAGE_VERSION,
            durable_sequence=4,
            terminal_sequence=4,
            terminal_status="completed",
        )


class _NetworkSessionContext:
    def __init__(self, execution, network_session) -> None:
        self.execution = execution
        self.network_session = network_session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def scalar(self, _statement):
        return self.execution

    async def get(self, _model, _identity):
        return self.network_session


class _NetworkSessionFactory:
    def __init__(self, execution, network_session) -> None:
        self.execution = execution
        self.network_session = network_session

    def __call__(self):
        return _NetworkSessionContext(self.execution, self.network_session)


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


def _journal_event(
    *,
    run_id,
    session_id,
    sequence: int,
    event_type: str,
    payload: dict,
) -> DurableRunEvent:
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
        session_id=session_id,
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
async def test_active_network_run_does_not_return_sql_running_after_durable_terminal() -> None:
    execution_id = uuid4()
    project_id = uuid4()
    network_id = uuid4()
    network_session_id = uuid4()
    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        network_id=network_id,
        network_session_id=network_session_id,
        status="running",
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
    )
    network_session = SimpleNamespace(id=network_session_id, project_id=project_id)
    service = object.__new__(JournalAwareNetworkBoundaryService)
    service._session_factory = _NetworkSessionFactory(execution, network_session)
    service._run_event_journal = _TerminalJournal(execution_id, "network")
    service._authorize_execution = AsyncMock(return_value=None)

    active = await service.active_execution(
        principal=None,
        network_session_id=network_session_id,
        network_id=network_id,
        environment=None,
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
    network_session_id = uuid4()
    invocation_id = uuid4()
    agent_run_id = uuid4()
    journal = InMemoryRunEventJournal()
    await journal.write_batch(
        [
            _journal_event(
                run_id=execution_id,
                session_id=network_session_id,
                sequence=1,
                event_type="run.attempt.started",
                payload={},
            ),
            _journal_event(
                run_id=execution_id,
                session_id=network_session_id,
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
                session_id=network_session_id,
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
    assert frame.session_id == network_session_id
    assert frame.data["invocations"][0]["agent_run_id"] == str(agent_run_id)
    await stream.aclose()


@pytest.mark.asyncio
async def test_playground_composer_excludes_terminal_journal_run(monkeypatch) -> None:
    monkeypatch.setenv("WOOBE_ENCRYPTION_KEY", "test" * 8)
    monkeypatch.setenv("WOOBE_SECRET_KEY", "test" * 8)
    from modules.agent.composition.composers import (
        agent_run_reattach_composer as composer,
    )

    run = _direct_run()
    monkeypatch.setattr(composer, 'AgentRuntimeTransactionRunner', lambda *args: _Transactions(run))
    monkeypatch.setattr(composer, 'EXECUTION_STATE_STORE', InMemoryExecutionStateStore())
    monkeypatch.setattr(composer, 'RUN_EVENT_JOURNAL', _TerminalJournal(run.id))

    active = await composer.active_agent_run_composer()(
        session_id=run.session_id, principal=_principal(run),
    )
    assert active is None


@pytest.mark.asyncio
async def test_active_agent_does_not_hide_terminal_outside_durable_prefix() -> None:
    from dataclasses import replace

    run = _direct_run()
    journal = _TerminalJournal(run.id)
    state = await journal.get_state(run.id)
    journal.get_state = AsyncMock(return_value=replace(state, durable_sequence=3))
    service = AgentRunReattachService(
        transactions=_Transactions(run), state_store=InMemoryExecutionStateStore(), journal=journal,
    )
    active = await service.active(session_id=run.session_id, principal=_principal(run))
    assert active['run_id'] == str(run.id)
