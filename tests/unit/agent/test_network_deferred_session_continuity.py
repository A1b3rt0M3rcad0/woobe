from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.infra.execution import transaction_bounded_structured_output as runtime_module
from modules.agent.infra.execution.transaction_bounded_structured_output import (
    TransactionBoundedStructuredOutputRuntime,
)


class _SessionRepository:
    async def get_by_id(self, _session_id):
        return None


class _Repositories:
    def __init__(self) -> None:
        self.provider_credentials = SimpleNamespace()
        self.sessions = _SessionRepository()
        self.messages = SimpleNamespace()


class _CountingTransactions:
    def __init__(self) -> None:
        self.repositories = _Repositories()
        self.read_calls = 0
        self.write_calls = 0
        self.read_active = False

    async def read(self, operation):
        self.read_calls += 1
        self.read_active = True
        try:
            return await operation(self.repositories, SimpleNamespace())
        finally:
            self.read_active = False

    async def run(self, _operation):
        self.write_calls += 1
        raise AssertionError("Deferred Network preparation must not open a write transaction")


class _ExecutionStateStore:
    def __init__(self, transactions: _CountingTransactions, state: dict) -> None:
        self._transactions = transactions
        self._state = dict(state)
        self.get_calls = []
        self.created = []

    async def get(self, run_id):
        assert not self._transactions.read_active, (
            "Network Redis state must be read only after the SQL read scope closes"
        )
        self.get_calls.append(run_id)
        return dict(self._state)

    async def create(self, run_id, state, *, ttl_seconds):
        assert not self._transactions.read_active
        self.created.append((run_id, dict(state), ttl_seconds))


class _Runtime(TransactionBoundedStructuredOutputRuntime):
    def __init__(self, *, transactions, project_id, agent_id) -> None:
        self._test_project_id = project_id
        self._test_agent_id = agent_id
        super().__init__(
            transactions=transactions,
            llm_factory=SimpleNamespace(),
            encryption_key="test-encryption-key",
        )

    async def _load_agent(self, _repositories, _input_dto):
        return SimpleNamespace(
            id=self._test_agent_id,
            project_id=self._test_project_id,
            fallback_credential_id=None,
            session_mode="stateful",
            settings={},
        )

    async def _load_credential(self, _repository, _agent):
        return SimpleNamespace(metadata={})

    def _decrypt_api_key(self, _credential):
        return "provider-key"

    def _resolve_base_url(self, _agent, _credential):
        return None

    def _get_response_format(self, _agent):
        return {"enabled": False}

    async def _load_rag_context(self, _agent, _query, _transactions):
        return None, []

    def _build_messages(
        self,
        _agent,
        _rag_context,
        history,
        user_message,
        _response_format,
    ):
        return [*history, HumanMessage(content=user_message)]


async def _prepare_tool_state(*_args, **_kwargs):
    return [], {}


async def _prepare_rag_binding(*_args, **_kwargs):
    return None


def _input(*, project_id, agent_id, session_id):
    return AskInput(
        project_id=project_id,
        agent_id=agent_id,
        session_id=session_id,
        message="second question",
        execution_context="playground",
        metadata={
            "source": "network_runtime",
            "defer_persistence": True,
        },
    )


@pytest.mark.asyncio
async def test_deferred_stateful_invocation_reuses_hot_session_without_postgres_write(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_module, "prepare_tool_state", _prepare_tool_state)
    monkeypatch.setattr(runtime_module, "prepare_rag_binding", _prepare_rag_binding)

    project_id = uuid4()
    agent_id = uuid4()
    network_execution_id = uuid4()
    previous_invocation_id = uuid4()
    current_invocation_id = uuid4()
    session_id = uuid4()

    transactions = _CountingTransactions()
    state_store = _ExecutionStateStore(
        transactions,
        {
            f"invocation:{previous_invocation_id}": {
                "id": str(previous_invocation_id),
                "agent_id": str(agent_id),
                "agent_session_id": str(session_id),
                "status": "completed",
                "input_message": "first question",
                "output_message": "first answer",
                "tool_calls": [
                    {
                        "tool_call_id": "call-1",
                        "tool_name": "lookup",
                        "input": {"customer": "42"},
                        "output": {"status": "active"},
                    }
                ],
            },
            f"invocation:{current_invocation_id}": {
                "id": str(current_invocation_id),
                "agent_id": str(agent_id),
                "agent_session_id": str(session_id),
                "status": "running",
                "input_message": "second question",
            },
        },
    )
    runtime = _Runtime(
        transactions=transactions,
        project_id=project_id,
        agent_id=agent_id,
    )
    runtime.configure_execution_state_store(state_store)

    context = new_execution_context()
    context.network_execution_id = network_execution_id
    context.network_invocation_id = current_invocation_id
    token = current_execution.set(context)
    try:
        prepared = await runtime._prepare_deferred_network(
            _input(
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
            )
        )
    finally:
        current_execution.reset(token)

    session = prepared[1]
    history = prepared[12]
    messages = prepared[11]

    assert session is not None
    assert session.id == session_id
    assert transactions.read_calls == 1
    assert transactions.write_calls == 0
    assert state_store.get_calls == [network_execution_id]
    assert state_store.created[-1][0] == current_invocation_id

    assert [type(message) for message in history] == [
        HumanMessage,
        AIMessage,
        ToolMessage,
    ]
    assert history[0].content == "first question"
    assert history[1].content == "first answer"
    assert history[1].tool_calls[0]["name"] == "lookup"
    assert json.loads(history[2].content) == {"status": "active"}
    assert isinstance(messages[-1], HumanMessage)
    assert messages[-1].content == "second question"


@pytest.mark.asyncio
async def test_missing_sql_session_requires_completed_hot_invocation_proof(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_module, "prepare_tool_state", _prepare_tool_state)
    monkeypatch.setattr(runtime_module, "prepare_rag_binding", _prepare_rag_binding)

    project_id = uuid4()
    agent_id = uuid4()
    network_execution_id = uuid4()
    current_invocation_id = uuid4()
    session_id = uuid4()

    transactions = _CountingTransactions()
    state_store = _ExecutionStateStore(
        transactions,
        {
            f"invocation:{current_invocation_id}": {
                "id": str(current_invocation_id),
                "agent_id": str(agent_id),
                "agent_session_id": str(session_id),
                "status": "running",
                "input_message": "second question",
            }
        },
    )
    runtime = _Runtime(
        transactions=transactions,
        project_id=project_id,
        agent_id=agent_id,
    )
    runtime.configure_execution_state_store(state_store)

    context = new_execution_context()
    context.network_execution_id = network_execution_id
    context.network_invocation_id = current_invocation_id
    token = current_execution.set(context)
    try:
        with pytest.raises(ValueError, match="Pinned Agent Session was not found"):
            await runtime._prepare_deferred_network(
                _input(
                    project_id=project_id,
                    agent_id=agent_id,
                    session_id=session_id,
                )
            )
    finally:
        current_execution.reset(token)

    assert transactions.read_calls == 1
    assert transactions.write_calls == 0
    assert state_store.get_calls == [network_execution_id]
    assert state_store.created == []
