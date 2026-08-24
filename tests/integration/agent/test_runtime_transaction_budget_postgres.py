from __future__ import annotations

from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import event
from sqlalchemy.orm import Session as SyncSession

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.infra.database.models import AgentModel, ProviderCredentialModel
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.execution.explicit_runtime_persistence import (
    TransactionalAskAgentUseCase,
)
from modules.core.infra.database.models import ProjectModel
from shared.infra.config import Settings
from shared.infra.crypto import encrypt_secret
from shared.infra.database.session import create_engine, create_session_factory


class _ProviderModel:
    async def ainvoke(self, _messages):
        response = AIMessage(content="two-commit answer")
        response.usage_metadata = {
            "input_tokens": 5,
            "output_tokens": 3,
            "total_tokens": 8,
        }
        response.response_metadata = {
            "provider": "openai",
            "model": "provider-mock",
        }
        return response


class _ProviderFactory:
    def __init__(self) -> None:
        self.model = _ProviderModel()

    def create_chat_model(self, **_kwargs):
        return self.model


@pytest.mark.asyncio
async def test_agent_happy_path_uses_exactly_two_postgres_commits() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    credential_id = uuid4()
    agent_id = uuid4()

    # Keep fixture ordering explicit. The ORM models do not expose relationships
    # that let SQLAlchemy infer the provider credential -> Agent dependency.
    async with session_factory() as session:
        async with session.begin():
            session.add(
                ProjectModel(
                    id=project_id,
                    workspace_id=uuid4(),
                    name="Transaction budget project",
                    slug=f"runtime-budget-{project_id}",
                    status="active",
                    data={},
                )
            )
            await session.flush()

            session.add(
                ProviderCredentialModel(
                    id=credential_id,
                    project_id=project_id,
                    provider="openai",
                    name="Transaction budget credential",
                    encrypted_secret=encrypt_secret(
                        "provider-mock-key",
                        settings.encryption_key,
                    ),
                    status="active",
                    meta={},
                )
            )
            await session.flush()

            session.add(
                AgentModel(
                    id=agent_id,
                    project_id=project_id,
                    provider_credential_id=credential_id,
                    fallback_credential_id=None,
                    name="Transaction budget agent",
                    description="",
                    type="assistant",
                    system_prompt="",
                    provider="openai",
                    model="provider-mock",
                    fallback_provider=None,
                    fallback_model=None,
                    temperature=0.2,
                    max_output_tokens=128,
                    session_mode="stateless",
                    status="active",
                    settings={},
                )
            )

    transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))
    runtime = TransactionalAskAgentUseCase(
        transactions,
        llm_factory=_ProviderFactory(),
        encryption_key=settings.encryption_key,
    )

    commits = 0

    def after_commit(_session) -> None:
        nonlocal commits
        commits += 1

    event.listen(SyncSession, "after_commit", after_commit)
    try:
        result = await runtime.execute(
            AskInput(
                project_id=project_id,
                agent_id=agent_id,
                message="count the durable boundaries",
                execution_context="playground",
            )
        )
    finally:
        event.remove(SyncSession, "after_commit", after_commit)

    assert result.answer == "two-commit answer"
    assert result.run_id is not None
    assert commits == 2, (
        "Agent happy path must persist only Acceptance and Finalization"
    )

    await engine.dispose()
