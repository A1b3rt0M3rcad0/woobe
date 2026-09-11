from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput, UsageInfo
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.entities import Agent, Session
from modules.agent.domain.enums import MessageRole, Provider
from modules.agent.infra.execution.event_journal_run_persistence import (
    EventJournalAgentRunPersistence,
)
from modules.agent.infra.execution.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict, bool]] = []

    async def emit(self, event_type: str, payload: dict, *, durable: bool = False):
        self.events.append((event_type, dict(payload), durable))
        return SimpleNamespace(sequence=len(self.events))


class _Messages:
    def __init__(self) -> None:
        self.items = {}

    async def get_by_id(self, message_id):
        return self.items.get(message_id)

    async def create(self, message):
        assert message.id not in self.items
        self.items[message.id] = message
        return message


class _Sessions:
    def __init__(self) -> None:
        self.updated = []

    async def update(self, session):
        self.updated.append(session)
        return session


class _Outbox:
    def __init__(self) -> None:
        self.events = []

    async def write(self, event):
        self.events.append(event)


class _Transactions:
    def __init__(self, repositories, outbox) -> None:
        self.repositories = repositories
        self.outbox = outbox
        self.calls = 0

    async def run(self, operation):
        self.calls += 1
        return await operation(self.repositories, self.outbox)


@pytest.mark.anyio
async def test_event_journal_completion_persists_assistant_message_before_return() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    session = Session(
        id=uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        runtime_environment="draft",
    )
    agent = Agent(
        id=agent_id,
        project_id=project_id,
        provider=Provider.custom,
        model="deepseek-v4-flash",
    )
    messages = _Messages()
    sessions = _Sessions()
    outbox = _Outbox()
    owner = StructuredOutputAskAgentUseCase.__new__(StructuredOutputAskAgentUseCase)
    owner._transactions = _Transactions(
        SimpleNamespace(messages=messages, sessions=sessions),
        outbox,
    )

    async def _hot_terminal_pending(**_kwargs):
        return None

    async def _hot_persisted(_status: str):
        return None

    owner._hot_terminal_pending = _hot_terminal_pending
    owner._hot_persisted = _hot_persisted

    execution = InstrumentedExecution(
        result=None,
        llm_calls=[
            {
                "call_id": str(uuid4()),
                "latency_ms": 25,
                "cost_status": "known",
            }
        ],
    )
    recorder = _Recorder()
    context = new_execution_context()
    context.run_id = uuid4()
    context.execution_context = "draft"
    context.execution = execution
    context.run_event_recorder = recorder
    token = current_execution.set(context)
    try:
        output = await EventJournalAgentRunPersistence().complete(
            owner,
            session=session,
            agent=agent,
            input_dto=AskInput(
                project_id=project_id,
                agent_id=agent_id,
                session_id=session.id,
                message="Olá",
                execution_context="draft",
            ),
            trace_id=uuid4(),
            answer="Olá. Sou o agente de Faturamento e Contas.",
            usage=UsageInfo(
                input_tokens=10,
                output_tokens=8,
                total_tokens=18,
                cost_usd=0.001,
            ),
            response_model=agent.model,
            response_provider=agent.provider.value,
            sources=[],
            parsed_output=None,
            output_parse_error=None,
            execution=execution,
            fallback_used=False,
            fallback_info=None,
            prepare_latency_ms=0,
            usage_complete=True,
            cost_status="known",
        )
    finally:
        current_execution.reset(token)

    assert output.message_id is not None
    persisted = messages.items[output.message_id]
    assert persisted.session_id == session.id
    assert persisted.role == MessageRole.ASSISTANT
    assert persisted.content == "Olá. Sou o agente de Faturamento e Contas."
    assert persisted.input_tokens == 10
    assert persisted.output_tokens == 8
    assert persisted.cost_usd == 0.001
    assert sessions.updated == [session]
    assert owner._transactions.calls == 1

    completed_events = [event for event in recorder.events if event[0] == "run.completed"]
    assert len(completed_events) == 1
    assert completed_events[0][1]["message_id"] == str(output.message_id)
    assert completed_events[0][2] is True
    assert [event.event_type for event in outbox.events] == [
        "agent.execution.message.created.v1"
    ]
