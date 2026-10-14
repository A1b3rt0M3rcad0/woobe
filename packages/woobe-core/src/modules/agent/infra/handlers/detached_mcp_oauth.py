"""OAuth flow I/O over a detached Tool, with owner-authorized CAS persistence."""
from copy import deepcopy
from uuid import UUID

from modules.agent.application.interfaces.project_configuration import configuration_for_session
from modules.agent.application.interfaces.tool_types import is_mcp_tool_type
from modules.agent.domain.errors import ToolNotFoundError
from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository
from modules.agent.infra.handlers.configured_tool_operation import ConfiguredToolOperation
from shared.contracts.project_configuration import ConfigurationError


class DetachedOAuthToolRepository:
    """A request-local workset, never a SQL repository or a global cache."""
    def __init__(self, tool):
        self.tool = deepcopy(tool)
        self.changed = False

    async def get_by_id(self, tool_id):
        if tool_id != self.tool.id:
            raise ToolNotFoundError(tool_id)
        return deepcopy(self.tool)

    async def update(self, tool):
        if tool.id != self.tool.id or tool.project_id != self.tool.project_id:
            raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
        self.tool = deepcopy(tool)
        self.changed = True
        return deepcopy(self.tool)


class DetachedMcpOAuthOperation:
    def __init__(self, uow_factory, controller_factory):
        self.uow_factory = uow_factory
        self.controller_factory = controller_factory

    async def __call__(self, request):
        tool_id = UUID(str((request.body or {}).get('tool_id')))
        async with self.uow_factory() as uow:
            await ConfiguredToolOperation.authorize(uow.session, request.principal, tool_id, 'tool:write')
            repository = SQLAlchemyAgentToolRepository(uow.session)
            tool = await repository.get_by_id(tool_id)
            configuration = configuration_for_session(uow.session)
            if configuration is None:
                raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
            await configuration.lock_project(tool.project_id)
            tool = await repository.lock_by_id(tool_id)
            if not is_mcp_tool_type(tool.type):
                raise ConfigurationError('CONFIG_BINDING_INVALID')
            original_config, original_updated_at = deepcopy(tool.config), tool.updated_at
            workset = DetachedOAuthToolRepository(tool)
        # Metadata discovery, client registration, token exchange and MCP
        # discovery all run after the authorization transaction has closed.
        result = await self.controller_factory(workset).handle(request)
        if not workset.changed:
            return result
        async with self.uow_factory() as uow:
            await ConfiguredToolOperation.authorize(uow.session, request.principal, tool_id, 'tool:write')
            configuration = configuration_for_session(uow.session)
            if configuration is None:
                raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
            await configuration.lock_project(tool.project_id)
            repository = SQLAlchemyAgentToolRepository(uow.session)
            current = await repository.lock_by_id(tool_id)
            if current.config != original_config or current.updated_at != original_updated_at:
                raise ConfigurationError('CONFIG_REVISION_CONFLICT')
            # Apply only flow-owned configuration. A detached stale name/status
            # must never replace concurrent metadata even when config is equal.
            current.config = deepcopy(workset.tool.config)
            await repository.update(current)
        return result
