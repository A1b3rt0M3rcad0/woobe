from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.composers.tool_runtime_factory import build_tool_runtime_registry
from modules.agent.application.mcp_discovery import DiscoverMcpToolsUseCase
from modules.agent.application.runtime_tool_use_cases import (
    RuntimeExecuteToolUseCase,
    RuntimeTestToolUseCase,
)
from modules.agent.application.use_cases.tools_use_cases import (
    CreateSecretUseCase,
    CreateToolUseCase,
    DeleteToolUseCase,
    ListSecretsUseCase,
    ListToolsByAgentUseCase,
    ListToolsUseCase,
    UpdateToolStatusUseCase,
    UpdateToolUseCase,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_secret_controller import CreateSecretController
from modules.agent.presentation.controllers.create_tool_controller import CreateToolController
from modules.agent.presentation.controllers.delete_tool_controller import DeleteToolController
from modules.agent.presentation.controllers.discover_mcp_tools_controller import DiscoverMcpToolsController
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
from shared.messaging.outbox_writer import OutboxEventWriter


def _agent_outbox(uow: AgentUnitOfWork) -> OutboxEventWriter:
    return cast(OutboxEventWriter, SQLAlchemyAgentOutboxEventWriter(uow))


def create_tool_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = CreateToolUseCase(uow.tools, _agent_outbox(uow))
    controller = CreateToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def update_tool_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = UpdateToolUseCase(uow.tools, _agent_outbox(uow))
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
    use_case = UpdateToolStatusUseCase(uow.tools, _agent_outbox(uow))
    controller = UpdateToolStatusController(use_case)
    return TransactionalHandler(uow, controller.handle)


def test_tool_composer(
    session_factory: async_sessionmaker[AsyncSession],
    executor: HttpToolExecutor | None = None,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    registry = build_tool_runtime_registry(
        settings=settings,
        executor=executor or get_http_tool_executor(),
    )
    use_case = RuntimeTestToolUseCase(runtime_registry=registry)
    controller = TestToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def discover_mcp_tools_composer(
    session_factory: async_sessionmaker[AsyncSession],
    executor: HttpToolExecutor | None = None,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = DiscoverMcpToolsUseCase(executor or get_http_tool_executor())
    controller = DiscoverMcpToolsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def execute_tool_composer(
    session_factory: async_sessionmaker[AsyncSession],
    executor: HttpToolExecutor | None = None,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    cipher = SecretCipherAdapter(settings.encryption_key)
    resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
    registry = build_tool_runtime_registry(
        settings=settings,
        executor=executor or get_http_tool_executor(),
        secret_resolver=resolver,
    )
    use_case = RuntimeExecuteToolUseCase(
        tool_repo=uow.tools,
        runtime_registry=registry,
    )
    controller = ExecuteToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def create_secret_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    cipher = SecretCipherAdapter(settings.encryption_key)
    use_case = CreateSecretUseCase(
        uow.tool_secrets,
        _agent_outbox(uow),
        cipher,
    )
    controller = CreateSecretController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_secrets_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ListSecretsUseCase(uow.tool_secrets)
    controller = ListSecretsController(use_case)
    return TransactionalHandler(uow, controller.handle)
