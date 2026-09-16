from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.instrumented_fallback_mixin import InstrumentedFallbackMixin
from modules.agent.infra.execution.runtime_streaming import current_runtime_stream
from modules.agent.infra.execution.structured_json_repair import repair_json_if_needed
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _Outbox:
    async def write(self, _event) -> None:
        return None


class _RunRepository:
    def __init__(self, run: AgentRun) -> None:
        self.run = run

    async def get_by_id(self, run_id):
        return self.run if self.run.id == run_id else None

    async def save(self, run):
        self.run = run
        return run


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        self.repositories = SimpleNamespace(runs=_RunRepository(run))
        self.outbox = _Outbox()

    async def run(self, operation):
        return await operation(self.repositories, self.outbox)

    async def read(self, operation):
        return await operation(self.repositories, self.outbox)


class _Chunk:
    def __init__(self, content: str = "") -> None:
        self.content = content
        self.tool_calls = []
        self.tool_call_chunks = []

    def __add__(self, other: "_Chunk") -> "_Chunk":
        return _Chunk(self.content + other.content)


class _BlockingModel:
    def __init__(self, first_chunk: str) -> None:
        self.first_chunk = first_chunk
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def astream(self, _messages):
        yield _Chunk(self.first_chunk)
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class _Factory:
    def __init__(self, model: _BlockingModel) -> None:
        self.model = model
        self.kwargs = None

    def create_chat_model(self, **kwargs):
        self.kwargs = kwargs
        return self.model


class _FallbackUseCase(InstrumentedFallbackMixin):
    def __init__(self, run: AgentRun, store: InMemoryExecutionStateStore) -> None:
        self.run = run
        self.store = store
        self.model = _BlockingModel("fallback partial")
        self._llm_factory = _Factory(self.model)

    async def execute(self, input_dto):
        del input_dto
        channel = current_runtime_stream.get()
        assert channel is not None
        channel.bind_execution(
            trace_id=self.run.trace_id,
            session_id=self.run.session_id,
            project_id=self.run.project_id,
            agent_id=self.run.agent_id,
        )
        setattr(channel, "run_id", self.run.id)
        await self.store.create(
            self.run.id,
            {
                "status": "running",
                "session_id": str(self.run.session_id),
            },
            ttl_seconds=3600,
        )
        await channel.emit(
            "meta",
            run_id=str(self.run.id),
            trace_id=str(self.run.trace_id),
            project_id=str(self.run.project_id),
            agent_id=str(self.run.agent_id),
        )
        agent = SimpleNamespace(
            provider="custom",
            model="primary-model",
            fallback_provider="custom",
            fallback_model="fallback-model",
            fallback_credential_id=None,
            fallback_provider_model_id=None,
            temperature=0.2,
            max_output_tokens=256,
            settings={},
        )
        await self._try_fallback(agent, [], False, "primary failed")
        raise AssertionError("fallback should be interrupted by cancellation")


class _JsonRepairUseCase:
    def __init__(self, run: AgentRun, store: InMemoryExecutionStateStore) -> None:
        self.run = run
        self.store = store
        self.model = _BlockingModel('{"answer":')
        self.factory = _Factory(self.model)

    async def execute(self, input_dto):
        del input_dto
        channel = current_runtime_stream.get()
        assert channel is not None
        channel.bind_execution(
            trace_id=self.run.trace_id,
            session_id=self.run.session_id,
            project_id=self.run.project_id,
            agent_id=self.run.agent_id,
        )
        setattr(channel, "run_id", self.run.id)
        await self.store.create(
            self.run.id,
            {
                "status": "running",
                "session_id": str(self.run.session_id),
            },
            ttl_seconds=3600,
        )
        await channel.emit(
            "meta",
            run_id=str(self.run.id),
            trace_id=str(self.run.trace_id),
            project_id=str(self.run.project_id),
            agent_id=str(self.run.agent_id),
        )
        execution = InstrumentedExecution(
            result=SimpleNamespace(content="not valid json"),
        )
        await repair_json_if_needed(
            execution=execution,
            call_index=1,
            llm_factory=self.factory,
            provider="custom",
            model_name="repair-model",
            api_key="test-key",
            base_url=None,
            max_tokens=256,
            schema={"type": "object"},
            clean_json_answer=lambda value: value,
        )
        raise AssertionError("JSON repair should be interrupted by cancellation")


def _run() -> AgentRun:
    return AgentRun(
        session_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="cancel special phase",
        execution_snapshot={},
    )


def _input(run: AgentRun) -> AskInput:
    return AskInput(
        project_id=run.project_id,
        agent_id=run.agent_id,
        message=run.input_message,
        execution_context="playground",
    )


async def _next_frame(stream, event_type: str) -> str:
    while True:
        frame = await asyncio.wait_for(anext(stream), timeout=2)
        if f"event: {event_type}" in frame:
            return frame


@pytest.mark.asyncio
async def test_cancel_interrupts_real_fallback_streaming_path() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    use_case = _FallbackUseCase(run, store)
    transactions = _Transactions(run)
    service = AskAgentStreamService(use_case, transactions, state_store=store)

    stream = service.stream(_input(run))
    try:
        await _next_frame(stream, "meta")
        await asyncio.wait_for(use_case.model.started.wait(), timeout=1)
        await store.request_cancel(run.id)

        terminal = await _next_frame(stream, "cancelled")
        assert '"persisted": true' in terminal
        assert '"output": "fallback partial"' in terminal
        await asyncio.wait_for(use_case.model.cancelled.wait(), timeout=1)
        assert transactions.repositories.runs.run.status == AgentRunStatus.CANCELLED
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_cancel_interrupts_real_json_repair_streaming_path_without_public_partial() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    use_case = _JsonRepairUseCase(run, store)
    transactions = _Transactions(run)
    service = AskAgentStreamService(use_case, transactions, state_store=store)

    stream = service.stream(_input(run))
    try:
        await _next_frame(stream, "meta")
        await asyncio.wait_for(use_case.model.started.wait(), timeout=1)
        await store.request_cancel(run.id)

        terminal = await _next_frame(stream, "cancelled")
        assert '"persisted": true' in terminal
        assert '"output": ""' in terminal
        await asyncio.wait_for(use_case.model.cancelled.wait(), timeout=1)
        assert transactions.repositories.runs.run.status == AgentRunStatus.CANCELLED
        assert transactions.repositories.runs.run.result is not None
        assert transactions.repositories.runs.run.result["partial"] is False
    finally:
        await stream.aclose()
