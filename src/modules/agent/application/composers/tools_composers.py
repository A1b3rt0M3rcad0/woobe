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
from modules.agent.presentation.controllers.create_secret_controller import CreateSecretController
from modules.agent.presentation.controllers.create_tool_controller import CreateToolController
from modules.agent.presentation.controllers.delete_tool_controller import DeleteToolController
from modules.agent.presentation.controllers.execute_tool_controller import ExecuteToolController
from modules.agent.presentation.controllers.list_secrets_controller import ListSecretsController
from modules.agent.presentation.controllers.list_tools_by_agent_controller import (
    ListToolsByAgentController,
)
from modules.agent.presentation.controllers.list_tools_controller import ListToolsController
from modules.agent.presentation.controllers.test_tool_controller import TestToolController
from modules.agent.presentation.controllers.update_tool_controller import UpdateToolController
from modules.agent.presentation.controllers.update_tool_status_controller import (
    UpdateToolStatusController,
)
from shared.infra.config import Settings
from shared.infra.transactional_handler import TransactionalHandler


def create_tool_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = CreateToolUseCase(uow.tools, outbox)
    controller = CreateToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def update_tool_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = UpdateToolUseCase(uow.tools, outbox)
    controller = UpdateToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def delete_tool_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = DeleteToolUseCase(uow.tools)
    controller = DeleteToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_tools_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ListToolsUseCase(uow.tools)
    controller = ListToolsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_tools_by_agent_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ListToolsByAgentUseCase(uow.tools)
    controller = ListToolsByAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)


def update_tool_status_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = UpdateToolStatusUseCase(uow.tools)
    controller = UpdateToolStatusController(use_case)
    return TransactionalHandler(uow, controller.handle)


def test_tool_composer(
    session_factory: async_sessionmaker[AsyncSession],
    executor: HttpToolExecutor,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = TestToolUseCase(uow.tools, executor)
    controller = TestToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def execute_tool_composer(
    session_factory: async_sessionmaker[AsyncSession],
    executor: HttpToolExecutor,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    cipher = SecretCipherAdapter(settings.encryption_key)
    resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
    use_case = ExecuteToolUseCase(
        tool_repo=uow.tools,
        tool_executor=executor,
        secret_resolver=resolver,
    )
    controller = ExecuteToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def create_secret_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    cipher = SecretCipherAdapter(settings.encryption_key)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = CreateSecretUseCase(uow.tool_secrets, cipher, outbox)
    controller = CreateSecretController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_secrets_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ListSecretsUseCase(uow.tool_secrets)
    controller = ListSecretsController(use_case)
    return TransactionalHandler(uow, controller.handle)
