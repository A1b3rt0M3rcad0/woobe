from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from modules.agent.application.dtos.runtime_dtos import AskInput, UsageInfo
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.entities import Agent, Message, Session
from modules.agent.domain.enums import MessageRole, Provider
from modules.agent.domain.errors import MessageNotFoundError
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
        message = self.items.get(message_id)
        if message is None:
            raise MessageNotFoundError(message_id)
        return message

    async def create(self, message):
        assert message.id not in self.items
        self.items[message.id] = message
        return message

    async def list_by_session(self, session_id):
        return [
            message
            for message in self.items.values()
            if message.session_id == session_id
        ]


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


async def _complete_turn(
    *,
    owner,
    project_id,
    agent,
    session,
    recorder,
    answer="Olá. Sou o agente de Faturamento e Contas.",
):
    call_id = str(uuid4())
    execution = InstrumentedExecution(
        result=None,
        llm_calls=[
            {
                "call_id": call_id,
                "latency_ms": 25,
                "cost_status": "known",
            }
        ],
        timeline=[
            {
                "kind": "llm",
                "occurred_at": "2026-09-21T12:00:00.025000+00:00",
                "payload": {
                    "call_id": call_id,
                    "call_index": 1,
                    "phase": "response_generation",
                    "status": "success",
                    "started_at": "2026-09-21T12:00:00+00:00",
                    "ended_at": "2026-09-21T12:00:00.025000+00:00",
                    "occurred_at": "2026-09-21T12:00:00.025000+00:00",
                    "latency_ms": 25,
                    "provider": "custom",
                    "model": "deepseek-v4-flash",
                    "input_tokens": 10,
                    "output_tokens": 8,
                    "total_tokens": 18,
                    "cost_usd": 0.001,
                    "cost_status": "known",
                    "usage_complete": True,
                },
            }
        ],
    )
    context = new_execution_context()
    context.prepare_started_at = "2026-09-21T11:59:59.990000+00:00"
    context.prepare_ended_at = "2026-09-21T12:00:00+00:00"
    context.prepare_latency_ms = 10
    context.run_id = uuid4()
    context.execution_context = "draft"
    context.execution = execution
    context.run_event_recorder = recorder
    token = current_execution.set(context)
    try:
        return await EventJournalAgentRunPersistence().complete(
            owner,
            session=session,
            agent=agent,
            input_dto=AskInput(
                project_id=project_id,
                agent_id=agent.id,
                session_id=session.id,
                message="Olá",
                execution_context="draft",
            ),
            trace_id=uuid4(),
            answer=answer,
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


def _owner(messages, sessions, outbox):
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
    return owner


def _fixtures():
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
    return project_id, agent, session


@pytest.mark.anyio
async def test_event_journal_completion_persists_assistant_message_before_return() -> None:
    project_id, agent, session = _fixtures()
    messages = _Messages()
    sessions = _Sessions()
    outbox = _Outbox()
    owner = _owner(messages, sessions, outbox)
    recorder = _Recorder()

    output = await _complete_turn(
        owner=owner,
        project_id=project_id,
        agent=agent,
        session=session,
        recorder=recorder,
    )

    assert output.message_id is not None
    persisted = messages.items[output.message_id]
    assert persisted.session_id == session.id
    assert persisted.role == MessageRole.ASSISTANT
    assert persisted.content == "Olá. Sou o agente de Faturamento e Contas."
    assert persisted.input_tokens == 10
    assert persisted.output_tokens == 8
    assert persisted.cost_usd == 0.001
    assert persisted.data is not None
    assert persisted.data["run_id"] == str(output.run_id)
    assert persisted.data["trace_id"] == str(output.trace_id)
    assert persisted.data["provider"] == "custom"
    assert persisted.data["model"] == "deepseek-v4-flash"
    assert persisted.data["tool_calls"] == []
    assert persisted.data["sources"] == []
    assert persisted.data["parsed_output"] is None
    assert persisted.data["output_parse_error"] is None
    assert persisted.data["cancelled"] is False
    assert persisted.data["partial"] is False
    assert sessions.updated == [session]
    assert owner._transactions.calls == 1

    completed_events = [event for event in recorder.events if event[0] == "run.completed"]
    assert len(completed_events) == 1
    completed_payload = completed_events[0][1]
    assert completed_payload["message_id"] == str(output.message_id)
    assert completed_payload["timeline_complete"] is True
    assert output.execution_events == completed_payload["execution_events"]
    event_types = {
        event["event_type"] for event in completed_payload["execution_events"]
    }
    assert {
        "http.request.received",
        "agent.execution.started",
        "agent.prepare.started",
        "agent.prepare.completed",
        "llm.call.started",
        "llm.call.completed",
        "structured_output.parse.completed",
        "agent.execution.completed",
        "http.response.prepared",
    } <= event_types
    assert completed_events[0][2] is True
    assert [event.event_type for event in outbox.events] == [
        "agent.execution.message.created.v1"
    ]


@pytest.mark.anyio
async def test_next_turn_history_contains_completed_assistant_turn_without_waiting_for_projector() -> None:
    project_id, agent, session = _fixtures()
    messages = _Messages()
    sessions = _Sessions()
    outbox = _Outbox()
    owner = _owner(messages, sessions, outbox)
    recorder = _Recorder()

    user_message = Message(
        project_id=project_id,
        agent_id=agent.id,
        session_id=session.id,
        role=MessageRole.USER,
        content="Olá",
    )
    await messages.create(user_message)

    output = await _complete_turn(
        owner=owner,
        project_id=project_id,
        agent=agent,
        session=session,
        recorder=recorder,
        answer="Olá. Como posso ajudar?",
    )

    assert output.message_id in messages.items
    history = await owner._load_history(messages, session)

    assert len(history) == 2
    assert isinstance(history[0], HumanMessage)
    assert history[0].content == "Olá"
    assert isinstance(history[1], AIMessage)
    assert history[1].content == "Olá. Como posso ajudar?"
