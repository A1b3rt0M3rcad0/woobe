from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.domain.entities import Message
from modules.agent.domain.enums import MessageRole
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.execution.run_event_projector import AgentRunEventProjector
from shared.contracts.run_event_journal import DurableRunEvent
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


class FakeRuns:
    def __init__(self, run: AgentRun) -> None:
        self.run = run
        self.save_calls = 0

    async def get_by_id_for_update(self, run_id):
        return self.run if self.run.id == run_id else None

    async def save(self, run):
        self.run = run
        self.save_calls += 1
        return run


class FakeMessages:
    def __init__(self) -> None:
        self.items = {}
        self.create_calls = 0

    async def get_by_id(self, message_id):
        return self.items.get(message_id)

    async def create(self, message):
        self.create_calls += 1
        self.items[message.id] = message
        return message


class FakeSessions:
    def __init__(self, session) -> None:
        self.session = session
        self.update_calls = 0

    async def get_by_id(self, session_id):
        return self.session if self.session.id == session_id else None

    async def update(self, session):
        self.session = session
        self.update_calls += 1
        return session


class FakeOutbox:
    def __init__(self) -> None:
        self.events = []

    async def write(self, event):
        self.events.append(event)


class FakeTransactions:
    def __init__(self, repositories, outbox) -> None:
        self.repositories = repositories
        self.outbox = outbox

    async def run(self, operation):
        return await operation(self.repositories, self.outbox)


def completed_event(run: AgentRun, message_id) -> DurableRunEvent:
    return DurableRunEvent(
        run_id=run.id,
        run_kind="agent",
        sequence=1,
        event_id=str(uuid4()),
        event_type="run.completed",
        occurred_at="2026-09-10T18:10:00+00:00",
        schema_version=1,
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        metadata={"project_id": str(run.project_id), "agent_id": str(run.agent_id)},
        payload={
            "run_id": str(run.id),
            "trace_id": str(run.trace_id),
            "project_id": str(run.project_id),
            "agent_id": str(run.agent_id),
            "session_id": str(run.session_id),
            "message_id": str(message_id),
            "answer": "projected answer",
            "provider": "custom",
            "model": "deepseek-v4-flash",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "cost_usd": 0.001,
            },
            "diagnostics": {
                "llm_call_count": 1,
                "tool_call_count": 0,
                "agent_runtime_latency_ms": 250,
                "usage_complete": True,
                "cost_status": "known",
            },
            "llm_calls": [
                {
                    "call_id": str(uuid4()),
                    "call_index": 0,
                    "phase": "response_generation",
                    "provider": "custom",
                    "model": "deepseek-v4-flash",
                    "status": "completed",
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                }
            ],
            "tool_calls": [],
            "sources": [{"document_id": "doc-1"}],
            "completed_at": "2026-09-10T18:10:00+00:00",
        },
    )


def _run_fixture():
    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    run = AgentRun(
        project_id=project_id,
        agent_id=agent_id,
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="hello",
        execution_snapshot={},
        session_id=session_id,
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
    )
    session = SimpleNamespace(
        id=session_id,
        project_id=project_id,
        agent_id=agent_id,
        last_message_at=None,
    )
    return run, session


@pytest.mark.anyio
async def test_agent_projector_materializes_terminal_read_model_and_message_once() -> None:
    run, session = _run_fixture()
    messages = FakeMessages()
    sessions = FakeSessions(session)
    runs = FakeRuns(run)
    outbox = FakeOutbox()
    projector = AgentRunEventProjector(
        FakeTransactions(
            SimpleNamespace(runs=runs, messages=messages, sessions=sessions),
            outbox,
        )
    )
    message_id = uuid4()
    event = completed_event(run, message_id)

    await projector.project([event])
    await projector.project([event])

    assert runs.run.status == AgentRunStatus.COMPLETED
    assert runs.run.journal_projected_sequence == 1
    assert runs.run.output_message_id == message_id
    assert runs.run.result["answer"] == "projected answer"
    assert runs.run.result["provider"] == "custom"
    assert runs.run.result["model"] == "deepseek-v4-flash"
    assert runs.run.result["diagnostics"]["llm_call_count"] == 1
    assert runs.run.result["llm_calls"][0]["total_tokens"] == 15
    assert runs.run.result["sources"][0]["document_id"] == "doc-1"
    assert runs.run.usage["total_tokens"] == 15
    assert messages.items[message_id].content == "projected answer"
    assert messages.create_calls == 1
    assert sessions.update_calls == 1
    assert runs.save_calls == 1
    assert [item.event_type for item in outbox.events] == [
        "agent.execution.message.created.v1",
        "agent.execution.completed.v1",
    ]


@pytest.mark.anyio
async def test_agent_projector_reuses_synchronously_materialized_assistant_message() -> None:
    run, session = _run_fixture()
    messages = FakeMessages()
    sessions = FakeSessions(session)
    runs = FakeRuns(run)
    outbox = FakeOutbox()
    projector = AgentRunEventProjector(
        FakeTransactions(
            SimpleNamespace(runs=runs, messages=messages, sessions=sessions),
            outbox,
        )
    )
    message_id = uuid4()
    messages.items[message_id] = Message(
        id=message_id,
        project_id=run.project_id,
        agent_id=run.agent_id,
        session_id=run.session_id,
        role=MessageRole.ASSISTANT,
        content="projected answer",
    )

    await projector.project([completed_event(run, message_id)])

    assert messages.create_calls == 0
    assert sessions.update_calls == 0
    assert runs.run.status == AgentRunStatus.COMPLETED
    assert runs.run.output_message_id == message_id
    assert runs.run.journal_projected_sequence == 1
    assert [item.event_type for item in outbox.events] == [
        "agent.execution.completed.v1",
    ]


@pytest.mark.anyio
async def test_agent_projector_rejects_projection_gaps() -> None:
    run = AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="hello",
        execution_snapshot={},
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
    )
    repositories = SimpleNamespace(
        runs=FakeRuns(run),
        messages=FakeMessages(),
        sessions=FakeSessions(SimpleNamespace(id=uuid4())),
    )
    projector = AgentRunEventProjector(FakeTransactions(repositories, FakeOutbox()))
    event = DurableRunEvent(
        run_id=run.id,
        run_kind="agent",
        sequence=2,
        event_id=str(uuid4()),
        event_type="execution.started",
        occurred_at="2026-09-10T18:10:00+00:00",
        schema_version=1,
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        metadata={},
        payload={},
    )

    with pytest.raises(RuntimeError, match="projection gap"):
        await projector.project([event])
