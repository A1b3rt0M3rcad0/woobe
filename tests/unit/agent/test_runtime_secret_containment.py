from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.entities import Agent, ProviderCredential, Tool
from modules.agent.domain.enums import Provider, SessionMode, ToolStatus, ToolType
from modules.agent.infra.execution import explicit_runtime_persistence as persistence_module
from modules.agent.infra.execution.explicit_runtime_persistence import (
    TransactionalAskAgentUseCase,
)
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _Outbox:
    def __init__(self) -> None:
        self.events = []

    async def write(self, event) -> None:
        self.events.append(event)


class _Runs:
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


class _Transactions:
    def __init__(self, repositories) -> None:
        self.repositories = repositories
        self.outbox = _Outbox()
        self.write_calls = 0

    async def run(self, operation):
        self.write_calls += 1
        return await operation(self.repositories, self.outbox)


class _Runtime(TransactionalAskAgentUseCase):
    def __init__(self, transactions, agent, credential) -> None:
        self._test_agent = agent
        self._test_credential = credential
        super().__init__(transactions=transactions, llm_factory=SimpleNamespace())

    async def _load_agent(self, _repositories, _input_dto):
        return self._test_agent

    async def _load_credential(self, _repository, _agent):
        return self._test_credential

    async def _resolve_session(self, _repository, _input_dto, _agent):
        return SimpleNamespace(id=uuid4())

    async def _save_user_message(self, *_args, **_kwargs):
        return SimpleNamespace(id=uuid4())

    def _decrypt_api_key(self, _credential):
        return "provider-key-in-memory"

    def _resolve_base_url(self, _agent, _credential):
        return None

    def _get_response_format(self, _agent):
        return {"enabled": False}

    async def _load_rag_context(self, _agent, _query, _transactions):
        return None, []

    def _build_messages(self, *_args, **_kwargs):
        return []


def _json(value) -> str:
    return json.dumps(value, default=str, sort_keys=True)


@pytest.mark.asyncio
async def test_decrypted_tool_secret_exists_only_in_execution_memory(monkeypatch) -> None:
    project_id = uuid4()
    agent_id = uuid4()
    credential_id = uuid4()
    tool_id = uuid4()
    plaintext = "TOP-SECRET-DO-NOT-PERSIST"

    tool = Tool(
        id=tool_id,
        project_id=project_id,
        agent_id=agent_id,
        name="private_api",
        type=ToolType.HTTP,
        status=ToolStatus.ACTIVE,
        config={
            "url": "https://example.test/private",
            "method": "GET",
            "headers": {"Authorization": "Bearer {{secret:API_TOKEN}}"},
        },
        input_schema={"type": "object", "properties": {}},
    )
    agent = Agent(
        id=agent_id,
        project_id=project_id,
        provider_credential_id=credential_id,
        name="secret-boundary-agent",
        system_prompt="test",
        provider=Provider.openai,
        model="test-model",
        session_mode=SessionMode.stateless,
        settings={"runtime_config": {"tools": {"tool_ids": [str(tool_id)]}}},
    )
    credential = ProviderCredential(
        id=credential_id,
        project_id=project_id,
        provider=Provider.openai,
        encrypted_secret="encrypted-provider-key",
    )
    runs = _Runs()

    async def get_tool(requested_id):
        return tool if requested_id == tool_id else None

    async def get_secret(_project_id, name):
        assert name == "API_TOKEN"
        return SimpleNamespace(encrypted_value="encrypted-tool-secret")

    repositories = SimpleNamespace(
        environment=SimpleNamespace(assert_enabled=_noop),
        provider_credentials=SimpleNamespace(get_by_id=_none),
        tools=SimpleNamespace(get_by_id=get_tool, list_by_agent=_empty),
        tool_secrets=SimpleNamespace(get_by_name=get_secret),
        knowledge_versions=SimpleNamespace(get_by_id=_none),
        vector_snapshots=SimpleNamespace(get_by_id=_none, list_snapshot_documents=_empty),
        provider_models=SimpleNamespace(get_by_id=_none),
        sessions=SimpleNamespace(),
        messages=SimpleNamespace(),
        runs=runs,
    )
    transactions = _Transactions(repositories)
    state_store = InMemoryExecutionStateStore()
    runtime = _Runtime(transactions, agent, credential)
    runtime.configure_execution_state_store(state_store)

    def decrypt_secret(ciphertext, _key):
        if ciphertext == "encrypted-tool-secret":
            return plaintext
        raise AssertionError(f"unexpected ciphertext: {ciphertext}")

    monkeypatch.setattr(persistence_module, "decrypt_secret", decrypt_secret)

    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent_id,
        message="use the private api",
        execution_context="playground",
    )
    context = new_execution_context()
    token = current_execution.set(context)
    try:
        await runtime._prepare(input_dto)
    finally:
        current_execution.reset(token)

    assert transactions.write_calls == 1
    assert context.prepared_tool_secrets == {"API_TOKEN": plaintext}
    assert context.run_id is not None

    run = runs.items[context.run_id]
    hot_state = await state_store.get(context.run_id)
    outbox_payloads = [getattr(event, "payload", {}) for event in transactions.outbox.events]

    persisted_surfaces = _json(
        {
            "execution_snapshot": run.execution_snapshot,
            "hot_state": hot_state,
            "outbox": outbox_payloads,
        }
    )
    assert plaintext not in persisted_surfaces
    assert "encrypted-tool-secret" not in persisted_surfaces
    assert "{{secret:API_TOKEN}}" in _json(run.execution_snapshot)


async def _noop(*_args, **_kwargs):
    return None


async def _none(*_args, **_kwargs):
    return None


async def _empty(*_args, **_kwargs):
    return []
