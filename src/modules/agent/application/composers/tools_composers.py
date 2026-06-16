from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.tools_use_cases import (
    CreateSecretUseCase,
    CreateToolUseCase,
    DeleteToolUseCase,
    ExecuteToolUseCase,
    ListSecretsUseCase,
    ListToolsByAgentUseCase,
    ListToolsUseCase,
    TestToolUseCase,
    UpdateToolStatusUseCase,
    UpdateToolUseCase,
)
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config import Settings


def create_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> CreateToolUseCase:
    uow = AgentUnitOfWork(session_factory)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    return CreateToolUseCase(uow.tools, outbox)


def update_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> UpdateToolUseCase:
    uow = AgentUnitOfWork(session_factory)
    return UpdateToolUseCase(uow.tools)


def delete_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> DeleteToolUseCase:
    uow = AgentUnitOfWork(session_factory)
    return DeleteToolUseCase(uow.tools)


def list_tools_composer(session_factory: async_sessionmaker[AsyncSession]) -> ListToolsUseCase:
    uow = AgentUnitOfWork(session_factory)
    return ListToolsUseCase(uow.tools)


def list_tools_by_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> ListToolsByAgentUseCase:
    uow = AgentUnitOfWork(session_factory)
    return ListToolsByAgentUseCase(uow.tools)


def update_tool_status_composer(session_factory: async_sessionmaker[AsyncSession]) -> UpdateToolStatusUseCase:
    uow = AgentUnitOfWork(session_factory)
    return UpdateToolStatusUseCase(uow.tools)


def test_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> TestToolUseCase:
    uow = AgentUnitOfWork(session_factory)
    executor = HttpToolExecutor()
    return TestToolUseCase(uow.tools, executor)


def execute_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> ExecuteToolUseCase:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings()
    executor = HttpToolExecutor()
    cipher = SecretCipherAdapter(settings.encryption_key)
    resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
    return ExecuteToolUseCase(tool_repo=uow.tools, tool_executor=executor, secret_resolver=resolver)


def create_secret_composer(session_factory: async_sessionmaker[AsyncSession]) -> CreateSecretUseCase:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings()
    cipher = SecretCipherAdapter(settings.encryption_key)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    return CreateSecretUseCase(uow.tool_secrets, cipher, outbox)


def list_secrets_composer(session_factory: async_sessionmaker[AsyncSession]) -> ListSecretsUseCase:
    uow = AgentUnitOfWork(session_factory)
    return ListSecretsUseCase(uow.tool_secrets)
