from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.domain.enums import MessageRole
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
        self.save_calls = 0

    async def get_by_id(self, run_id):
        return self.run if self.run.id == run_id else None

    async def get_by_id_for_update(self, run_id):
        return await self.get_by_id(run_id)

    async def save(self, run):
        self.run = run
        self.save_calls += 1
        return run


class _SessionRepository:
    def __init__(self, session_id) -> None:
        self.session = SimpleNamespace(id=session_id, last_message_at=None)
        self.update_calls = 0

    async def get_by_id(self, session_id):
        return self.session if self.session.id == session_id else None

    async def update(self, session):
        self.session = session
        self.update_calls += 1
        return session


class _MessageRepository:
    def __init__(self, user_content: str) -> None:
        self.messages = [
            SimpleNamespace(
                role=MessageRole.USER,
                content=user_content,
                data=None,
            )
        ]

    async def create(self, message):
        self.messages.append(message)
        return message


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        assert run.session_id is not None
        self.runs = _RunRepository(run)
        self.sessions = _SessionRepository(run.session_id)
        self.messages = _MessageRepository(run.input_message)
        self.repositories = SimpleNamespace(
            runs=self.runs,
            sessions=self.sessions,
            messages=self.messages,
        )
        self.outbox = _Outbox()
        self.write_calls = 0

    async def run(self, operation):
        self.write_calls += 1
        return await operation(self.repositories, self.outbox)

    async def read(self, operation):
        return await operation(self.repositories, self.outbox)


def _run() -> AgentRun:
    return AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="persist this user request",
        execution_snapshot={},
    )


def _input(run: AgentRun) -> AskInput:
    return AskInput(
        project_id=run.project_id,
        agent_id=run.agent_id,
        session_id=run.session_id,
        message=run.input_message,
        execution_context="playground",
    )


def _channel(run: AgentRun) -> RuntimeStreamChannel:
    channel = RuntimeStreamChannel()
    channel.bind_execution(
        trace_id=run.trace_id,
        session_id=run.session_id,
        project_id=run.project_id,
        agent_id=run.agent_id,
    )
    setattr(channel, "run_id", run.id)
    return channel


@pytest.mark.asyncio
async def test_cancel_after_partial_output_keeps_user_turn_and_persists_partial_assistant() -> None:
    run = _run()
    transactions = _Transactions(run)
    service = AskAgentStreamService(
        SimpleNamespace(),
        transactions,
        state_store=InMemoryExecutionStateStore(),
    )
    channel = _channel(run)
    channel.public_output = "partial assistant answer"
    channel.latest_usage = {
        "input_tokens": 12,
        "output_tokens": 4,
        "total_tokens": 16,
    }

    persisted = await service._persist_cancelled(
        channel,
        _input(run),
        "cancel_requested",
    )

    assert persisted is True
    assert transactions.runs.run.status == AgentRunStatus.CANCELLED
    assert transactions.runs.run.result["answer"] == "partial assistant answer"
    assert transactions.runs.run.result["partial"] is True
    assert transactions.runs.run.result["cancelled"] is True

    user_messages = [
        message
        for message in transactions.messages.messages
        if message.role == MessageRole.USER
    ]
    assistant_messages = [
        message
        for message in transactions.messages.messages
        if message.role == MessageRole.ASSISTANT
    ]

    assert len(user_messages) == 1
    assert user_messages[0].content == run.input_message
    assert len(assistant_messages) == 1
    assert assistant_messages[0].content == "partial assistant answer"
    assert assistant_messages[0].data["cancelled"] is True
    assert assistant_messages[0].data["partial"] is True
    assert assistant_messages[0].data["run_id"] == str(run.id)
    assert assistant_messages[0].data["trace_id"] == str(run.trace_id)
    assert transactions.sessions.update_calls == 1
    assert transactions.sessions.session.last_message_at is not None

    repeated = await service._persist_cancelled(
        channel,
        _input(run),
        "cancel_requested",
    )

    assert repeated is False
    assert len(transactions.messages.messages) == 2


@pytest.mark.asyncio
async def test_cancel_before_first_token_keeps_user_turn_without_empty_assistant_message() -> None:
    run = _run()
    transactions = _Transactions(run)
    service = AskAgentStreamService(
        SimpleNamespace(),
        transactions,
        state_store=InMemoryExecutionStateStore(),
    )
    channel = _channel(run)

    persisted = await service._persist_cancelled(
        channel,
        _input(run),
        "cancel_requested",
    )

    assert persisted is True
    assert transactions.runs.run.status == AgentRunStatus.CANCELLED
    assert transactions.runs.run.result["answer"] == ""
    assert transactions.runs.run.result["partial"] is False
    assert [message.role for message in transactions.messages.messages] == [MessageRole.USER]
    assert transactions.sessions.update_calls == 0
