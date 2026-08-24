from __future__ import annotations

from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.infra.execution.explicit_runtime_persistence import (
    TransactionalAskAgentUseCase as AskAgentUseCase,
)
from modules.agent.infra.database.models import AgentModel, ProviderCredentialModel
from modules.agent.infra.database.repositories import (
    SQLAlchemyMessageRepository,
    SQLAlchemySessionRepository,
)
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.core.infra.database.models import ProjectModel
from shared.infra.config import Settings
from shared.infra.crypto import encrypt_secret
from shared.infra.database.session import create_engine, create_session_factory


class ProviderModel:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.invocations: list[list[object]] = []

    async def ainvoke(self, messages):
        self.invocations.append(list(messages))
        response = AIMessage(content=self.answer)
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


class ProviderFactory:
    def __init__(self, model: ProviderModel) -> None:
        self.model = model
        self.calls: list[dict] = []

    def create_chat_model(self, **kwargs):
        self.calls.append(kwargs)
        return self.model


@pytest.mark.asyncio
async def test_session_and_history_survive_new_use_case_and_database_connection() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))
    project_id = uuid4()
    credential_id = uuid4()
    agent_id = uuid4()

    async with session_factory() as db:
        db.add(
            ProjectModel(
                id=project_id,
                workspace_id=uuid4(),
                name="Reload test project",
                slug=f"reload-project-{project_id}",
                status="active",
                data={},
            )
        )
        await db.flush()
        db.add(
            ProviderCredentialModel(
                id=credential_id,
                project_id=project_id,
                provider="openai",
                name="Provider mock credential",
                encrypted_secret=encrypt_secret(
                    "provider-mock-key",
                    settings.encryption_key,
                ),
                status="active",
                meta={},
            )
        )
        await db.flush()
        db.add(
            AgentModel(
                id=agent_id,
                project_id=project_id,
                provider_credential_id=credential_id,
                fallback_credential_id=None,
                name="Reload test agent",
                description="",
                type="assistant",
                system_prompt="",
                provider="openai",
                model="provider-mock",
                fallback_provider=None,
                fallback_model=None,
                temperature=0.2,
                max_output_tokens=128,
                session_mode="stateful",
                status="active",
                settings={},
            )
        )
        await db.commit()

    first_model = ProviderModel("first assistant reply")
    first_result = await AskAgentUseCase(
        transactions,
        llm_factory=ProviderFactory(first_model),
        encryption_key=settings.encryption_key,
    ).execute(
        AskInput(
            project_id=project_id,
            agent_id=agent_id,
            message="first user message",
            execution_context="playground",
        )
    )
    assert first_result.session_id is not None

    second_model = ProviderModel("second assistant reply")
    second_result = await AskAgentUseCase(
        transactions,
        llm_factory=ProviderFactory(second_model),
        encryption_key=settings.encryption_key,
    ).execute(
        AskInput(
            project_id=project_id,
            agent_id=agent_id,
            session_id=first_result.session_id,
            message="second user message",
            execution_context="playground",
        )
    )
    assert second_result.session_id == first_result.session_id

    provider_history = [
        (type(message).__name__, str(getattr(message, "content", "")))
        for message in second_model.invocations[0]
    ]
    assert provider_history == [
        ("HumanMessage", "first user message"),
        ("AIMessage", "first assistant reply"),
        ("HumanMessage", "second user message"),
    ]

    async with session_factory() as reloaded_db:
        sessions = await SQLAlchemySessionRepository(reloaded_db).list_by_agent(
            project_id,
            agent_id,
        )
        messages = await SQLAlchemyMessageRepository(reloaded_db).list_by_session(
            first_result.session_id,
        )

    assert [session.id for session in sessions] == [first_result.session_id]
    assert [
        (
            message.role.value
            if hasattr(message.role, "value")
            else str(message.role),
            message.content,
        )
        for message in messages
    ] == [
        ("user", "first user message"),
        ("assistant", "first assistant reply"),
        ("user", "second user message"),
        ("assistant", "second assistant reply"),
    ]
    await engine.dispose()
