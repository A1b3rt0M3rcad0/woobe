from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from modules.agent.application.context_assembler_registry import build_runtime_context_assembler
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.infra.execution import transaction_bounded_structured_output as runtime_module
from modules.agent.infra.execution.instrumented_execution_runner import run_instrumented_execution
from modules.agent.infra.execution.transaction_bounded_structured_output import (
    TransactionBoundedStructuredOutputRuntime,
    _network_hot_session_history,
)
from shared.contracts.errors import ValidationError


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "values,invalid",
    [
        pytest.param({"name": "Alberto", "age": 18}, False, id="exposed-and-hidden"),
        pytest.param({"age": 18}, True, id="missing-required"),
        pytest.param({"name": "Alberto", "age": "18"}, True, id="invalid-type"),
        pytest.param({"name": "Alberto", "age": 18, "extra": 1}, True, id="undeclared"),
    ],
)
async def test_deferred_network_resolves_external_context_before_hot_state(
    monkeypatch, values, invalid,
) -> None:
    monkeypatch.setattr(runtime_module, "prepare_tool_state", _prepare_tool_state)
    monkeypatch.setattr(runtime_module, "prepare_rag_binding", _prepare_rag_binding)
    project_id, agent_id = uuid4(), uuid4()
    transactions = _CountingTransactions()
    runtime = _Runtime(transactions=transactions, project_id=project_id, agent_id=agent_id)
    state_store = _ExecutionStateStore(transactions, {})
    runtime.configure_execution_state_store(state_store)
    agent = await runtime._load_agent(None, None)
    agent.provider, agent.model = "custom", "test-model"
    agent.temperature, agent.max_output_tokens = 0.0, 1000
    agent.settings["external_context_contract"] = {
        "name": {
            "schema": {"type": "string"}, "required": True,
            "model": {"expose": True},
        },
        "age": {
            "schema": {"type": "integer"}, "required": True,
            "model": {"expose": False},
        },
        "language": {
            "schema": {"type": "string"}, "default": "pt-BR",
            "model": {"expose": True},
        },
    }
    monkeypatch.setattr(runtime, "_load_agent", AsyncMock(return_value=agent))
    request = _input(project_id=project_id, agent_id=agent_id, session_id=None)
    request.external_context = values
    context = new_execution_context()
    context.project_id, context.agent_id = project_id, agent_id
    context.network_execution_id, context.network_invocation_id = uuid4(), uuid4()
    token = current_execution.set(context)
    try:
        if invalid:
            with pytest.raises(ValidationError):
                await runtime._prepare_deferred_network(request)
            assert state_store.created == []
        else:
            prepared = await runtime._prepare_deferred_network(request)
            assert context.external_context_snapshot == {
                "name": "Alberto", "age": 18, "language": "pt-BR",
            }
            assert context.model_external_context == {"name": "Alberto", "language": "pt-BR"}
            model = SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content="ok")))
            await run_instrumented_execution(
                llm_factory=SimpleNamespace(create_chat_model=lambda **_kwargs: model),
                execute_single_tool=AsyncMock(side_effect=AssertionError("No Tool expected")),
                clean_json_answer=lambda value: value,
                agent=agent,
                api_key="fixture",
                base_url=None,
                response_format={},
                json_enabled=False,
                has_tools=False,
                agent_tools=[],
                tool_name_to_id={},
                messages=[SystemMessage(content="You are a support Agent."), *prepared[11]],
                context_assembler=build_runtime_context_assembler(),
            )
            model.ainvoke.assert_awaited_once()
            received = "\n".join(str(message.content) for message in model.ainvoke.await_args.args[0])
            assert "Alberto" in received
            assert "pt-BR" in received
            assert '"age"' not in received
        assert transactions.write_calls == 0
    finally:
        current_execution.reset(token)


def _input(*, project_id, agent_id, session_id, message="second question"):
    return AskInput(
        project_id=project_id,
        agent_id=agent_id,
        session_id=session_id,
        message=message,
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


def test_hot_session_history_keeps_all_successful_rounds_and_ignores_failed_attempts() -> None:
    session_id = uuid4()
    first = UUID("00000000-0000-7000-8000-000000000001")
    failed = UUID("00000000-0000-7000-8000-000000000002")
    second = UUID("00000000-0000-7000-8000-000000000003")
    third = UUID("00000000-0000-7000-8000-000000000004")

    history = _network_hot_session_history(
        {
            f"invocation:{first}": {
                "id": str(first),
                "agent_session_id": str(session_id),
                "status": "completed",
                "input_message": "q1",
                "output_message": "a1",
            },
            f"invocation:{failed}": {
                "id": str(failed),
                "agent_session_id": str(session_id),
                "status": "failed",
                "input_message": "q-failed",
                "error": "provider rejected request",
            },
            f"invocation:{second}": {
                "id": str(second),
                "agent_session_id": str(session_id),
                "status": "completed",
                "input_message": "q2",
                "output_message": "a2",
            },
            f"invocation:{third}": {
                "id": str(third),
                "agent_session_id": str(session_id),
                "status": "completed",
                "input_message": "q3",
                "output_message": "a3",
            },
        },
        session_id=session_id,
    )

    assert history is not None
    assert [message.content for message in history] == [
        "q1",
        "a1",
        "q2",
        "a2",
        "q3",
        "a3",
    ]
    assert all("failed" not in str(message.content) for message in history)


@pytest.mark.asyncio
async def test_third_stateful_invocation_reuses_two_completed_hot_rounds(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_module, "prepare_tool_state", _prepare_tool_state)
    monkeypatch.setattr(runtime_module, "prepare_rag_binding", _prepare_rag_binding)

    project_id = uuid4()
    agent_id = uuid4()
    network_execution_id = uuid4()
    session_id = uuid4()
    first = UUID("00000000-0000-7000-8000-000000000011")
    second = UUID("00000000-0000-7000-8000-000000000012")
    current = UUID("00000000-0000-7000-8000-000000000013")

    transactions = _CountingTransactions()
    state_store = _ExecutionStateStore(
        transactions,
        {
            f"invocation:{first}": {
                "id": str(first),
                "agent_id": str(agent_id),
                "agent_session_id": str(session_id),
                "status": "completed",
                "input_message": "first request",
                "output_message": "first result",
            },
            f"invocation:{second}": {
                "id": str(second),
                "agent_id": str(agent_id),
                "agent_session_id": str(session_id),
                "status": "completed",
                "input_message": "second request",
                "output_message": "second result",
            },
            f"invocation:{current}": {
                "id": str(current),
                "agent_id": str(agent_id),
                "agent_session_id": str(session_id),
                "status": "running",
                "input_message": "third request",
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
    context.network_invocation_id = current
    token = current_execution.set(context)
    try:
        prepared = await runtime._prepare_deferred_network(
            _input(
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
                message="third request",
            )
        )
    finally:
        current_execution.reset(token)

    history = prepared[12]
    messages = prepared[11]
    assert [message.content for message in history] == [
        "first request",
        "first result",
        "second request",
        "second result",
    ]
    assert messages[-1].content == "third request"
    assert transactions.write_calls == 0

