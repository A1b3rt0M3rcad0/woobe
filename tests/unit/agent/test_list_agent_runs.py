from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from modules.agent.application.use_cases.list_agent_runs import ListAgentRunsUseCase
from modules.agent.domain.run import AgentRun, AgentRunStatus
from shared.contracts.run_event_journal import DurableRunEvent, RunJournalState
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


class _Access:
    def __init__(self) -> None:
        self.calls = []

    async def require_user_access(self, *, user_id, project_id) -> None:
        self.calls.append((user_id, project_id))


class _Runs:
    def __init__(self, runs) -> None:
        self.runs = runs
        self.calls = []

    async def list_direct(
        self,
        *,
        project_id,
        agent_id,
        session_id=None,
        environment=None,
        limit=100,
    ):
        self.calls.append((project_id, agent_id, session_id, environment, limit))
        return self.runs


class _TerminalJournal:
    def __init__(self, event: DurableRunEvent) -> None:
        self.event = event

    async def get_state(self, run_id):
        if run_id != self.event.run_id:
            return None
        return RunJournalState(
            run_id=run_id,
            run_kind="agent",
            storage_version=EVENT_JOURNAL_STORAGE_VERSION,
            durable_sequence=self.event.sequence,
            terminal_sequence=self.event.sequence,
            terminal_status="completed",
        )

    async def list_events(
        self,
        run_id,
        *,
        after_sequence=0,
        through_sequence=None,
        limit=5000,
    ):
        if run_id != self.event.run_id or self.event.sequence <= after_sequence:
            return []
        if through_sequence is not None and self.event.sequence > through_sequence:
            return []
        return [self.event][:limit]


def _run(*, status: AgentRunStatus) -> AgentRun:
    started_at = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
    completed_at = None if status == AgentRunStatus.RUNNING else started_at + timedelta(seconds=2)
    return AgentRun(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="playground",
        input_message="hello",
        execution_snapshot={},
        status=status,
        usage={"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
        result={"provider": "custom", "model": "test-model"},
        started_at=started_at,
        completed_at=completed_at,
        created_at=started_at,
    )


def _completed_event(run: AgentRun) -> DurableRunEvent:
    return DurableRunEvent(
        run_id=run.id,
        run_kind="agent",
        sequence=4,
        event_id=str(uuid4()),
        event_type="run.completed",
        occurred_at="2026-08-28T12:00:02+00:00",
        schema_version=1,
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        metadata={},
        payload={
            "run_id": str(run.id),
            "trace_id": str(run.trace_id),
            "provider": "custom",
            "model": "deepseek-v4-flash",
            "usage": {
                "input_tokens": 840,
                "output_tokens": 86,
                "total_tokens": 926,
                "cost_usd": 0.0001,
            },
            "latency_ms": 1960,
            "started_at": "2026-08-28T12:00:00+00:00",
            "completed_at": "2026-08-28T12:00:02+00:00",
        },
    )


@pytest.mark.asyncio
async def test_list_agent_runs_returns_durable_status_and_runtime_identity() -> None:
    run = _run(status=AgentRunStatus.CANCELLED)
    access = _Access()
    runs = _Runs([run])
    use_case = ListAgentRunsUseCase(runs, access)
    user_id = uuid4()

    result = await use_case.execute(
        user_id=user_id,
        project_id=run.project_id,
        agent_id=run.agent_id,
        session_id=run.session_id,
        environment="draft",
        limit=25,
    )

    assert access.calls == [(user_id, run.project_id)]
    assert runs.calls == [
        (run.project_id, run.agent_id, run.session_id, "draft", 25)
    ]
    assert result == [
        {
            "id": str(run.id),
            "trace_id": str(run.trace_id),
            "project_id": str(run.project_id),
            "agent_id": str(run.agent_id),
            "session_id": str(run.session_id),
            "environment": "draft",
            "origin": "playground",
            "status": "cancelled",
            "input_message": "hello",
            "provider": "custom",
            "model": "test-model",
            "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
            "failure_code": None,
            "failure_detail": None,
            "latency_ms": 2000,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat(),
            "created_at": run.created_at.isoformat(),
            "updated_at": None,
        }
    ]


@pytest.mark.asyncio
async def test_list_agent_runs_does_not_show_running_after_terminal_is_durable() -> None:
    run = _run(status=AgentRunStatus.RUNNING)
    run.storage_version = EVENT_JOURNAL_STORAGE_VERSION
    run.journal_projected_sequence = 0
    run.result = None
    run.usage = None
    event = _completed_event(run)
    use_case = ListAgentRunsUseCase(
        _Runs([run]),
        _Access(),
        _TerminalJournal(event),
    )

    result = await use_case.execute(
        user_id=uuid4(),
        project_id=run.project_id,
        agent_id=run.agent_id,
        session_id=run.session_id,
        environment="draft",
    )

    assert result[0]["status"] == "completed"
    assert result[0]["provider"] == "custom"
    assert result[0]["model"] == "deepseek-v4-flash"
    assert result[0]["usage"]["total_tokens"] == 926
    assert result[0]["latency_ms"] == 1960
    assert result[0]["completed_at"] == "2026-08-28T12:00:02+00:00"
