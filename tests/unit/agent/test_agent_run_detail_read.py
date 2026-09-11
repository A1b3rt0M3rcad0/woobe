from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from modules.agent.application.use_cases.read_agent_run_context import (
    ReadAgentRunContextUseCase,
)
from modules.agent.domain.run import AgentRun, AgentRunStatus
from shared.contracts.errors import NotFoundError
from shared.contracts.run_event_journal import DurableRunEvent, RunJournalState
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


class _Runs:
    def __init__(
        self,
        run: AgentRun | None,
        output_message: str | None = None,
        model_invocations: list[dict] | None = None,
    ):
        self.run = run
        self.output_message = output_message
        self.model_invocations = (
            [{"id": "invocation-1"}]
            if model_invocations is None
            else model_invocations
        )

    async def get_by_id(self, run_id):
        return self.run if self.run and self.run.id == run_id else None

    async def get_by_trace_id(self, trace_id):
        return self.run if self.run and self.run.trace_id == trace_id else None

    async def get_output_message_content(self, message_id):
        if self.run and self.run.output_message_id == message_id:
            return self.output_message
        return None

    async def list_model_invocations(self, run_id):
        return self.model_invocations if self.run and self.run.id == run_id else []


class _Access:
    def __init__(self):
        self.calls: list[tuple[object, object]] = []

    async def require_user_access(self, *, user_id, project_id):
        self.calls.append((user_id, project_id))


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
        if run_id != self.event.run_id:
            return []
        if self.event.sequence <= after_sequence:
            return []
        if through_sequence is not None and self.event.sequence > through_sequence:
            return []
        return [self.event][:limit]


def _run() -> AgentRun:
    now = datetime.now(timezone.utc)
    return AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        agent_release_id=uuid4(),
        input_message_id=uuid4(),
        output_message_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="network_runtime",
        input_message="user request",
        execution_snapshot={"network_node_id": str(uuid4())},
        network_execution_id=uuid4(),
        network_invocation_id=uuid4(),
        parent_run_id=uuid4(),
        status=AgentRunStatus.COMPLETED,
        usage={"input_tokens": 120, "output_tokens": 30, "cost_usd": 0.001},
        result={
            "answer": "# Completed\n\nUseful result.",
            "provider": "custom",
            "model": "model-v1",
            "diagnostics": {"llm_call_count": 1, "agent_runtime_latency_ms": 250},
            "llm_calls": [{"call_index": 0, "phase": "response_generation"}],
            "tool_calls": [{"tool_name": "lookup", "status": "success"}],
            "sources": [{"document_id": "doc-1"}],
            "parsed_output": None,
            "output_parse_error": None,
        },
        started_at=now,
        completed_at=now,
    )


def _standalone_run() -> AgentRun:
    run = _run()
    run.origin = "runtime_api"
    run.network_execution_id = None
    run.network_invocation_id = None
    run.parent_run_id = None
    run.result = {
        "provider": "custom",
        "model": "standalone-v1",
        "agent_runtime_latency_ms": 420,
        "llm_work_latency_ms": 300,
        "tool_wall_latency_ms": 80,
        "tool_work_latency_ms": 70,
        "llm_call_count": 2,
        "tool_call_count": 1,
        "usage_complete": True,
        "cost_status": "known",
        "tool_calls": [{"tool_name": "search", "success": True}],
        "sources": [],
        "llm_calls": [{"call_index": 0}, {"call_index": 1}],
    }
    return run


def _terminal_event(run: AgentRun) -> DurableRunEvent:
    call_id = uuid4()
    snapshot_id = uuid4()
    contribution_id = uuid4()
    return DurableRunEvent(
        run_id=run.id,
        run_kind="agent",
        sequence=3,
        event_id=str(uuid4()),
        event_type="run.completed",
        occurred_at="2026-09-11T04:30:02+00:00",
        schema_version=1,
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        metadata={
            "project_id": str(run.project_id),
            "agent_id": str(run.agent_id),
            "trace_id": str(run.trace_id),
        },
        payload={
            "run_id": str(run.id),
            "trace_id": str(run.trace_id),
            "project_id": str(run.project_id),
            "agent_id": str(run.agent_id),
            "session_id": str(run.session_id),
            "answer": "Durable answer",
            "provider": "custom",
            "model": "deepseek-v4-flash",
            "usage": {
                "input_tokens": 840,
                "output_tokens": 86,
                "total_tokens": 926,
                "cost_usd": 0.0001,
            },
            "diagnostics": {
                "llm_call_count": 1,
                "tool_call_count": 0,
                "agent_runtime_latency_ms": 1960,
                "usage_complete": True,
                "cost_status": "known",
            },
            "llm_calls": [
                {
                    "call_id": str(call_id),
                    "call_index": 0,
                    "phase": "response_generation",
                    "provider": "custom",
                    "model": "deepseek-v4-flash",
                    "status": "completed",
                    "latency_ms": 1800,
                    "input_tokens": 840,
                    "output_tokens": 86,
                    "total_tokens": 926,
                    "cost_usd": 0.0001,
                    "context_snapshot": {
                        "id": str(snapshot_id),
                        "policy_schema_version": 1,
                        "policy_hash": "policy-hash",
                        "runtime_reserve_units": 0,
                        "estimated_input_units": 840,
                        "pressure_status": "OK",
                        "measurement_status": "reported",
                        "manifest": {},
                        "materialized_hash": "materialized-hash",
                        "retention_mode": "references_only",
                        "reproduction_level": "manifest_only",
                        "contributions": [
                            {
                                "id": str(contribution_id),
                                "ordinal": 0,
                                "source_type": "USER_INPUT",
                                "modality": "text",
                                "priority": "MANDATORY",
                                "materialized_units": 2,
                                "transformations": [],
                                "metadata": {},
                            }
                        ],
                    },
                }
            ],
            "tool_calls": [],
            "sources": [],
            "started_at": "2026-09-11T04:30:00+00:00",
            "completed_at": "2026-09-11T04:30:02+00:00",
            "latency_ms": 1960,
        },
    )


@pytest.mark.asyncio
async def test_agent_run_detail_reads_durable_network_run_without_observability_trace() -> None:
    run = _run()
    access = _Access()
    use_case = ReadAgentRunContextUseCase(_Runs(run), access)
    user_id = uuid4()

    detail = await use_case.detail_by_run(run_id=run.id, user_id=user_id)

    assert detail["id"] == str(run.id)
    assert detail["trace_id"] == str(run.trace_id)
    assert detail["network_execution_id"] == str(run.network_execution_id)
    assert detail["network_invocation_id"] == str(run.network_invocation_id)
    assert detail["answer"].startswith("# Completed")
    assert detail["diagnostics"]["llm_call_count"] == 1
    assert detail["diagnostics"]["successful_tool_calls"] == 1
    assert detail["tool_calls"][0]["tool_name"] == "lookup"
    assert detail["sources"][0]["document_id"] == "doc-1"
    assert detail["usage"]["input_tokens"] == 120
    assert detail["started_at"] == run.started_at.isoformat()
    assert access.calls == [(user_id, run.project_id)]


@pytest.mark.asyncio
async def test_agent_run_detail_normalizes_standalone_diagnostics_and_recovers_message_output() -> None:
    run = _standalone_run()
    markdown = "# Standalone result\n\nRecovered from the persisted assistant Message."
    access = _Access()
    use_case = ReadAgentRunContextUseCase(_Runs(run, output_message=markdown), access)
    user_id = uuid4()

    detail = await use_case.detail_by_trace(trace_id=run.trace_id, user_id=user_id)

    assert detail["origin"] == "runtime_api"
    assert detail["answer"] == markdown
    assert detail["diagnostics"]["agent_runtime_latency_ms"] == 420
    assert detail["diagnostics"]["llm_call_count"] == 2
    assert detail["diagnostics"]["tool_call_count"] == 1
    assert detail["diagnostics"]["successful_tool_calls"] == 1
    assert detail["diagnostics"]["failed_tool_calls"] == 0
    assert access.calls == [(user_id, run.project_id)]


@pytest.mark.asyncio
async def test_agent_run_detail_can_resolve_network_run_by_trace() -> None:
    run = _run()
    access = _Access()
    use_case = ReadAgentRunContextUseCase(_Runs(run), access)
    user_id = uuid4()

    detail = await use_case.detail_by_trace(trace_id=run.trace_id, user_id=user_id)

    assert detail["id"] == str(run.id)
    assert detail["origin"] == "network_runtime"
    assert access.calls == [(user_id, run.project_id)]


@pytest.mark.asyncio
async def test_agent_run_detail_prefers_durable_terminal_journal_while_postgres_projection_lags() -> None:
    run = _standalone_run()
    run.status = AgentRunStatus.RUNNING
    run.storage_version = EVENT_JOURNAL_STORAGE_VERSION
    run.journal_projected_sequence = 0
    run.result = None
    run.usage = None
    run.completed_at = None
    event = _terminal_event(run)
    use_case = ReadAgentRunContextUseCase(
        _Runs(run, model_invocations=[]),
        _Access(),
        _TerminalJournal(event),
    )
    user_id = uuid4()

    detail = await use_case.detail_by_run(run_id=run.id, user_id=user_id)
    invocations = await use_case.by_run(run_id=run.id, user_id=user_id)

    assert detail["status"] == "completed"
    assert detail["answer"] == "Durable answer"
    assert detail["provider"] == "custom"
    assert detail["model"] == "deepseek-v4-flash"
    assert detail["usage"]["total_tokens"] == 926
    assert detail["diagnostics"]["llm_call_count"] == 1
    assert detail["diagnostics"]["agent_runtime_latency_ms"] == 1960
    assert detail["completed_at"] == "2026-09-11T04:30:02+00:00"
    assert len(detail["llm_calls"]) == 1
    assert len(invocations) == 1
    assert invocations[0]["provider"] == "custom"
    assert invocations[0]["model"] == "deepseek-v4-flash"
    assert invocations[0]["total_units"] == 926
    assert invocations[0]["context_snapshot"]["measurement_status"] == "reported"
    assert invocations[0]["persistence"] == "agent_run_journal"


@pytest.mark.asyncio
async def test_agent_run_detail_returns_not_found_for_unknown_run() -> None:
    use_case = ReadAgentRunContextUseCase(_Runs(None), _Access())

    with pytest.raises(NotFoundError, match="Agent Run not found"):
        await use_case.detail_by_run(run_id=uuid4(), user_id=uuid4())
