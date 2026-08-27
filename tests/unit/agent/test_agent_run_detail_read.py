from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from modules.agent.application.use_cases.read_agent_run_context import (
    ReadAgentRunContextUseCase,
)
from modules.agent.domain.run import AgentRun, AgentRunStatus
from shared.contracts.errors import NotFoundError


class _Runs:
    def __init__(self, run: AgentRun | None):
        self.run = run

    async def get_by_id(self, run_id):
        return self.run if self.run and self.run.id == run_id else None

    async def get_by_trace_id(self, trace_id):
        return self.run if self.run and self.run.trace_id == trace_id else None

    async def list_model_invocations(self, run_id):
        return [{"id": "invocation-1"}] if self.run and self.run.id == run_id else []


class _Access:
    def __init__(self):
        self.calls: list[tuple[object, object]] = []

    async def require_user_access(self, *, user_id, project_id):
        self.calls.append((user_id, project_id))


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
    assert detail["tool_calls"][0]["tool_name"] == "lookup"
    assert detail["sources"][0]["document_id"] == "doc-1"
    assert detail["usage"]["input_tokens"] == 120
    assert detail["started_at"] == run.started_at.isoformat()
    assert access.calls == [(user_id, run.project_id)]


@pytest.mark.asyncio
async def test_agent_run_detail_can_resolve_standalone_run_by_trace() -> None:
    run = _run()
    access = _Access()
    use_case = ReadAgentRunContextUseCase(_Runs(run), access)
    user_id = uuid4()

    detail = await use_case.detail_by_trace(trace_id=run.trace_id, user_id=user_id)

    assert detail["id"] == str(run.id)
    assert detail["origin"] == "network_runtime"
    assert access.calls == [(user_id, run.project_id)]


@pytest.mark.asyncio
async def test_agent_run_detail_returns_not_found_for_unknown_run() -> None:
    use_case = ReadAgentRunContextUseCase(_Runs(None), _Access())

    with pytest.raises(NotFoundError, match="Agent Run not found"):
        await use_case.detail_by_run(run_id=uuid4(), user_id=uuid4())
