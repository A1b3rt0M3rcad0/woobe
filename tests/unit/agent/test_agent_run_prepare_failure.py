from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.entities import Agent, ProviderCredential
from modules.agent.domain.enums import Provider, SessionMode
from modules.agent.domain.run import AgentRunStatus
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
        self.environment = SimpleNamespace(assert_enabled=self._assert_enabled)
        self.provider_credentials = SimpleNamespace(get_by_id=self._none)
        self.tools = SimpleNamespace(list_by_agent=self._empty, get_by_id=self._none)
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


class _Transactions:
    def __init__(self) -> None:
        self.repositories = _Repositories()
        self.outbox = _Outbox()
        self.write_calls = 0

    async def run(self, operation):
        self.write_calls += 1
        return await operation(self.repositories, self.outbox)


class _Runtime(TransactionalAskAgentUseCase):
    def __init__(self, transactions: _Transactions) -> None:
        project_id = uuid4()
        credential_id = uuid4()
        self.agent = Agent(
            project_id=project_id,
            provider_credential_id=credential_id,
            name="prepare-failure-agent",
            system_prompt="",
            provider=Provider.openai,
            model="test-model",
            temperature=0.1,
            max_output_tokens=64,
            session_mode=SessionMode.stateless,
            settings={},
        )
        self.credential = ProviderCredential(
            id=credential_id,
            project_id=project_id,
            provider=Provider.openai,
            encrypted_secret="ciphertext",
        )
        super().__init__(transactions=transactions, llm_factory=SimpleNamespace())

    async def _load_agent(self, _repositories, _input_dto):
        return self.agent

    async def _load_credential(self, _repository, _agent):
        return self.credential

    async def _resolve_session(self, _repository, _input_dto, _agent):
        return None

    def _get_response_format(self, _agent):
        return {"enabled": False}

    def _decrypt_api_key(self, _credential):
        raise RuntimeError("decrypt failed after acceptance")


@pytest.mark.asyncio
async def test_prepare_failure_after_acceptance_terminalizes_agent_run() -> None:
    transactions = _Transactions()
    runtime = _Runtime(transactions)
    input_dto = AskInput(
        project_id=runtime.agent.project_id,
        agent_id=runtime.agent.id,
        message="trigger prepare failure",
        execution_context="playground",
    )
    context = new_execution_context()
    token = current_execution.set(context)
    try:
        with pytest.raises(RuntimeError, match="decrypt failed after acceptance"):
            await runtime.execute(input_dto)
    finally:
        current_execution.reset(token)

    assert context.run_id is not None
    assert transactions.write_calls == 2
    assert context.terminal_persisted is True

    persisted = transactions.repositories.runs.items[context.run_id]
    assert persisted.status == AgentRunStatus.FAILED
    assert persisted.failure_code == "prepare_failed"
    assert persisted.failure_detail == "decrypt failed after acceptance"
    assert persisted.completed_at is not None
    assert persisted.result is not None
    assert persisted.result["run_id"] == str(context.run_id)
    assert persisted.result["failure_phase"] == "prepare"
