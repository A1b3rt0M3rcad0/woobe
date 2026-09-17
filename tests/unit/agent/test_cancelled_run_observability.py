from __future__ import annotations

import time
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import RuntimeStreamChannel
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _Outbox:
    def __init__(self) -> None:
        self.events = []

    async def write(self, event) -> None:
        self.events.append(event)


class _RunRepository:
    def __init__(self, run: AgentRun) -> None:
        self.run = run

    async def get_by_id(self, run_id):
        return self.run if self.run.id == run_id else None

    async def save(self, run):
        self.run = run
        return run


class _SessionRepository:
    def __init__(self, session_id) -> None:
        self.session = SimpleNamespace(id=session_id, last_message_at=None)

    async def get_by_id(self, session_id):
        return self.session if self.session.id == session_id else None

    async def update(self, session):
        self.session = session
        return session


class _MessageRepository:
    def __init__(self) -> None:
        self.items = []

    async def create(self, message):
        self.items.append(message)
        return message


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        self.runs = _RunRepository(run)
        self.sessions = _SessionRepository(run.session_id)
        self.messages = _MessageRepository()
        self.repositories = SimpleNamespace(
            runs=self.runs,
            sessions=self.sessions,
            messages=self.messages,
        )
        self.outbox = _Outbox()

    async def run(self, operation):
        return await operation(self.repositories, self.outbox)

    async def read(self, operation):
        return await operation(self.repositories, self.outbox)


def _run() -> AgentRun:
    run = AgentRun(
        session_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="write a long answer",
        execution_snapshot={},
    )
    run.status = AgentRunStatus.RUNNING
    return run


def _input(run: AgentRun) -> AskInput:
    return AskInput(
        project_id=run.project_id,
        agent_id=run.agent_id,
        message=run.input_message,
        execution_context="playground",
    )


def _context_snapshot() -> dict:
    return {
        "id": str(uuid4()),
        "policy_schema_version": 1,
        "policy_hash": "cancel-observability-policy",
        "model_capacity_units": 128000,
        "reserved_output_units": 2048,
        "runtime_reserve_units": 0,
        "usable_input_budget": 125952,
        "estimated_input_units": 512,
        "reported_input_units": None,
        "utilization": 0.004,
        "pressure_status": "LOW",
        "measurement_status": "estimated",
        "manifest": {},
        "materialized_hash": "cancel-observability-context",
        "retention_mode": "references_only",
        "reproduction_level": "manifest_only",
        "contributions": [],
    }


def _cancelled_llm_call(*, latency_ms: int = 4100) -> dict:
    started = datetime.now(timezone.utc)
    return {
        "call_id": str(uuid4()),
        "call_index": 1,
        "phase": "capability_response_generation",
        "status": "cancelled",
        "error": None,
        "started_at": started.isoformat(),
        "ended_at": started.isoformat(),
        "occurred_at": started.isoformat(),
        "latency_ms": latency_ms,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
        "cost_status": "unknown_tokens",
        "cost_reason": "Model invocation was cancelled before final provider usage",
        "usage_complete": False,
        "provider": "custom",
        "model": "deepseek-v4-flash",
        "context_snapshot": _context_snapshot(),
        "provider_model_id": None,
        "provider_credential_id": None,
        "pricing_id": None,
        "pricing_snapshot": None,
    }


def _bind_live_execution(run: AgentRun, call: dict):
    context = new_execution_context()
    context.started_at = time.monotonic() - 5.0
    context.run_id = run.id
    context.trace_id = run.trace_id
    context.session_id = run.session_id
    context.project_id = run.project_id
    context.agent_id = run.agent_id
    context.execution_context = "playground"
    context.prepare_latency_ms = 80
    context.execution = InstrumentedExecution(
        result=None,
        llm_calls=[call],
        timeline=[
            {
                "kind": "llm",
                "occurred_at": call["occurred_at"],
                "payload": call,
            }
        ],
    )
    return current_execution.set(context)


@pytest.mark.asyncio
async def test_cancelled_agent_run_persists_live_execution_diagnostics() -> None:
    run = _run()
    transactions = _Transactions(run)
    service = AskAgentStreamService(
        SimpleNamespace(),
        transactions,
        state_store=InMemoryExecutionStateStore(),
    )
    channel = RuntimeStreamChannel()
    channel.bind_execution(
        trace_id=run.trace_id,
        session_id=run.session_id,
        project_id=run.project_id,
        agent_id=run.agent_id,
    )
    setattr(channel, "run_id", run.id)
    channel.public_output = "partial answer already visible"
    channel.latest_usage = {
        "input_tokens": 512,
        "output_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
    }
    call = _cancelled_llm_call()
    token = _bind_live_execution(run, call)
    try:
        persisted = await service._persist_cancelled(
            channel,
            _input(run),
            "cancel_requested",
        )
    finally:
        current_execution.reset(token)

    assert persisted is True
    assert transactions.runs.run.status == AgentRunStatus.CANCELLED
    assert transactions.runs.run.result is not None

    result = transactions.runs.run.result
    diagnostics = result.get("diagnostics")
    assert isinstance(diagnostics, dict)
    assert diagnostics["schema_version"] == 5
    assert diagnostics["llm_call_count"] == 1
    assert diagnostics["llm_work_latency_ms"] == 4100
    assert diagnostics["usage_complete"] is False
    assert diagnostics["cost_status"] == "unknown_tokens"

    assert len(result["llm_calls"]) == 1
    assert result["llm_calls"][0]["status"] == "cancelled"
    assert result["llm_calls"][0]["phase"] == "capability_response_generation"
    assert result["llm_calls"][0]["context_snapshot"]["policy_hash"] == (
        "cancel-observability-policy"
    )


@pytest.mark.asyncio
async def test_cancel_before_first_token_keeps_cancelled_invocation_and_context_evidence() -> None:
    run = _run()
    transactions = _Transactions(run)
    service = AskAgentStreamService(
        SimpleNamespace(),
        transactions,
        state_store=InMemoryExecutionStateStore(),
    )
    channel = RuntimeStreamChannel()
    channel.bind_execution(
        trace_id=run.trace_id,
        session_id=run.session_id,
        project_id=run.project_id,
        agent_id=run.agent_id,
    )
    setattr(channel, "run_id", run.id)
    call = _cancelled_llm_call(latency_ms=2300)
    token = _bind_live_execution(run, call)
    try:
        persisted = await service._persist_cancelled(
            channel,
            _input(run),
            "cancel_requested",
        )
    finally:
        current_execution.reset(token)

    assert persisted is True
    result = transactions.runs.run.result
    assert result is not None
    assert result["answer"] == ""
    assert result["partial"] is False
    assert result["cancelled"] is True

    diagnostics = result.get("diagnostics")
    assert isinstance(diagnostics, dict)
    assert diagnostics["llm_call_count"] == 1
    assert diagnostics["llm_work_latency_ms"] == 2300

    calls = result.get("llm_calls")
    assert isinstance(calls, list) and len(calls) == 1
    assert calls[0]["status"] == "cancelled"
    assert calls[0]["context_snapshot"]["id"]
    assert calls[0]["context_snapshot"]["estimated_input_units"] == 512
