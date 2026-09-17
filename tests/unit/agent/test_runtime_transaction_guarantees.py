from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.entities import Agent, ProviderCredential, Tool
from modules.agent.domain.enums import (
    Provider,
    SessionMode,
    ToolStatus,
    ToolType,
)
from modules.agent.infra.execution.explicit_runtime_persistence import (
    TransactionalAskAgentUseCase,
)


class _Outbox:
    def __init__(self) -> None:
        self.events = []

    async def write(self, event) -> None:
        self.events.append(event)


class _RunRepository:
    def __init__(self) -> None:
        self.items = {}

    async def create(self, run):
        self.items[run.id] = run
        return run

    async def get_by_id(self, run_id):
        return self.items.get(run_id)

    async def save(self, run):
        self.items[run.id] = run
        return run


class _Repositories:
    def __init__(self) -> None:
        self.tool_items = []
        self.environment = SimpleNamespace(assert_enabled=self._assert_enabled)
        self.provider_credentials = SimpleNamespace(get_by_id=self._none)
        self.tools = SimpleNamespace(list_by_agent=self._tools, get_by_id=self._none)
        self.tool_secrets = SimpleNamespace(get_by_name=self._none)
        self.knowledge_versions = SimpleNamespace(get_by_id=self._none)
        self.vector_snapshots = SimpleNamespace(
            get_by_id=self._none,
            list_snapshot_documents=self._empty,
        )
        self.provider_models = SimpleNamespace(get_by_id=self._none)
        self.sessions = SimpleNamespace()
        self.messages = SimpleNamespace()
        self.runs = _RunRepository()

    async def _assert_enabled(self, **_kwargs) -> None:
        return None

    async def _none(self, *_args, **_kwargs):
        return None

    async def _empty(self, *_args, **_kwargs):
        return []

    async def _tools(self, *_args, **_kwargs):
        return list(self.tool_items)


class _CountingTransactions:
    def __init__(self) -> None:
        self.repositories = _Repositories()
        self.outbox = _Outbox()
        self.write_calls = 0
        self.read_calls = 0
        self.active_write_scopes = 0
        self.active_read_scopes = 0

    @property
    def sql_scope_active(self) -> bool:
        return bool(self.active_write_scopes or self.active_read_scopes)

    async def run(self, operation):
        self.write_calls += 1
        self.active_write_scopes += 1
        try:
            return await operation(self.repositories, self.outbox)
        finally:
            self.active_write_scopes -= 1

    async def read(self, operation):
        self.read_calls += 1
        self.active_read_scopes += 1
        try:
            return await operation(self.repositories, self.outbox)
        finally:
            self.active_read_scopes -= 1


class _ChatModel:
    def __init__(self, transactions: _CountingTransactions, *, fail: bool = False) -> None:
        self._transactions = transactions
        self._fail = fail
        self.calls = 0

    async def ainvoke(self, _messages):
        assert not self._transactions.sql_scope_active, (
            "LLM execution must not run while a SQL UoW/read scope is active"
        )
        self.calls += 1
        if self._fail:
            raise RuntimeError("primary provider failed")
        return SimpleNamespace(
            content="ok",
            tool_calls=[],
            usage_metadata={
                "input_tokens": 2,
                "output_tokens": 3,
                "total_tokens": 5,
            },
            response_metadata={"model": "test-model", "provider": "openai"},
        )


class _LLMFactory:
    def __init__(self, transactions: _CountingTransactions, *, fallback: bool = False) -> None:
        self.transactions = transactions
        self.primary = _ChatModel(transactions, fail=fallback)
        self.fallback = _ChatModel(transactions)
        self.created = 0

    def create_chat_model(self, **_kwargs):
        self.created += 1
        return self.primary if self.created == 1 else self.fallback


class _ToolChatModel:
    def __init__(self, transactions: _CountingTransactions) -> None:
        self._transactions = transactions
        self.calls = 0
        self.bound_tools = None

    def bind_tools(self, tools, *, tool_choice):
        self.bound_tools = list(tools)
        assert tool_choice == "auto"
        return self

    async def ainvoke(self, _messages):
        assert not self._transactions.sql_scope_active, (
            "LLM Tool rounds must not run while a SQL scope is active"
        )
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "lookup",
                        "args": {"query": "customer"},
                    }
                ],
                usage_metadata={"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
                response_metadata={},
            )
        return SimpleNamespace(
            content="tool-ok",
            tool_calls=[],
            usage_metadata={"input_tokens": 4, "output_tokens": 2, "total_tokens": 6},
            response_metadata={"model": "test-model", "provider": "openai"},
        )


class _ToolLLMFactory:
    def __init__(self, transactions: _CountingTransactions) -> None:
        self.model = _ToolChatModel(transactions)

    def create_chat_model(self, **_kwargs):
        return self.model


class _Runtime(TransactionalAskAgentUseCase):
    def __init__(
        self,
        transactions,
        llm_factory,
        *,
        fallback: bool = False,
        tool_executor_factory=None,
    ) -> None:
        project_id = uuid4()
        credential_id = uuid4()
        fallback_credential_id = uuid4() if fallback else None
        self.agent = Agent(
            project_id=project_id,
            provider_credential_id=credential_id,
            fallback_credential_id=fallback_credential_id,
            name="runtime-boundary-test",
            system_prompt="You are a test agent.",
            provider=Provider.openai,
            model="test-model",
            fallback_provider=Provider.openai if fallback else None,
            fallback_model="fallback-model" if fallback else None,
            temperature=0.1,
            max_output_tokens=100,
            session_mode=SessionMode.stateless,
            settings={},
        )
        self.primary_credential = ProviderCredential(
            id=credential_id,
            project_id=project_id,
            provider=Provider.openai,
            encrypted_secret="unused",
        )
        self.fallback_credential = (
            ProviderCredential(
                id=fallback_credential_id,
                project_id=project_id,
                provider=Provider.openai,
                encrypted_secret="unused-fallback",
            )
            if fallback_credential_id
            else None
        )
        super().__init__(
            transactions=transactions,
            llm_factory=llm_factory,
            tool_executor_factory=tool_executor_factory,
        )

    async def _load_agent(self, _repositories, _input_dto):
        return self.agent

    async def _load_credential(self, _repository, _agent):
        return self.primary_credential

    async def _resolve_session(self, _repository, _input_dto, _agent):
        return SimpleNamespace(id=uuid4())

    async def _save_user_message(self, *_args, **_kwargs):
        return SimpleNamespace(id=uuid4())

    async def _do_save_assistant_message(self, *_args, **_kwargs):
        return SimpleNamespace(id=uuid4())

    def _decrypt_api_key(self, credential):
        assert not self._transactions.sql_scope_active, (
            "credential decryption must happen after Acceptance leaves the SQL scope"
        )
        if credential is self.fallback_credential:
            return "fallback-key"
        return "primary-key"

    def _resolve_base_url(self, _agent, _credential):
        return None

    def _resolve_base_url_for_provider(self, _provider, _credential, _settings):
        return None

    def _get_response_format(self, _agent):
        return {"enabled": False}

    def _build_messages(self, _agent, _rag, _history, message, _response_format):
        return [HumanMessage(content=message)]


@pytest.mark.asyncio
async def test_agent_happy_path_has_exactly_acceptance_and_finalization_writes() -> None:
    transactions = _CountingTransactions()
    llm_factory = _LLMFactory(transactions)
    runtime = _Runtime(transactions, llm_factory)
    input_dto = AskInput(
        project_id=runtime.agent.project_id,
        agent_id=runtime.agent.id,
        message="hello",
        execution_context="playground",
    )
    context = new_execution_context()
    token = current_execution.set(context)
    try:
        result = await runtime.execute(input_dto)
    finally:
        current_execution.reset(token)

    assert result.answer == "ok"
    assert transactions.write_calls == 2
    assert transactions.read_calls == 0
    assert llm_factory.primary.calls == 1
    assert context.terminal_persisted is True
    persisted = transactions.repositories.runs.items[context.run_id]
    assert persisted.status.value == "completed"


@pytest.mark.asyncio
async def test_prepared_tool_execution_adds_no_sql_transaction() -> None:
    transactions = _CountingTransactions()
    tool = Tool(
        project_id=uuid4(),
        name="lookup",
        type=ToolType.FUNCTION,
        status=ToolStatus.ACTIVE,
        config={},
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
        },
    )
    tool_calls = []

    async def execute_tool(tool_id, input_data):
        assert not transactions.sql_scope_active, (
            "Tool execution must not run while a SQL scope is active"
        )
        assert tool_id == tool.id
        tool_calls.append((tool_id, dict(input_data)))
        return {"success": True, "output": {"customer": "ok"}}

    llm_factory = _ToolLLMFactory(transactions)
    runtime = _Runtime(
        transactions,
        llm_factory,
        tool_executor_factory=execute_tool,
    )
    tool.project_id = runtime.agent.project_id
    tool.agent_id = runtime.agent.id
    transactions.repositories.tool_items = [tool]

    context = new_execution_context()
    token = current_execution.set(context)
    try:
        result = await runtime.execute(
            AskInput(
                project_id=runtime.agent.project_id,
                agent_id=runtime.agent.id,
                message="lookup customer",
                execution_context="playground",
            )
        )
    finally:
        current_execution.reset(token)

    assert result.answer == "tool-ok"
    assert transactions.write_calls == 2
    assert transactions.read_calls == 0
    assert tool_calls == [(tool.id, {"query": "customer"})]
    assert llm_factory.model.calls == 2


@pytest.mark.asyncio
async def test_prepared_fallback_adds_no_sql_transaction() -> None:
    transactions = _CountingTransactions()
    llm_factory = _LLMFactory(transactions, fallback=True)
    runtime = _Runtime(transactions, llm_factory, fallback=True)
    transactions.repositories.provider_credentials.get_by_id = (
        lambda _credential_id: _async_value(runtime.fallback_credential)
    )
    input_dto = AskInput(
        project_id=runtime.agent.project_id,
        agent_id=runtime.agent.id,
        message="use fallback",
        execution_context="playground",
    )
    context = new_execution_context()
    token = current_execution.set(context)
    try:
        result = await runtime.execute(input_dto)
    finally:
        current_execution.reset(token)

    assert result.fallback_used is True
    assert transactions.write_calls == 2
    assert transactions.read_calls == 0
    assert llm_factory.primary.calls == 1
    assert llm_factory.fallback.calls == 1


async def _async_value(value):
    return value
