"""Compatibility entrypoints for centrally configured, persisted Tools.

Selection and lease acquisition are transactional. Network I/O uses a detached
definition and the same per-send resolver as accepted Agent Runs.
"""
from uuid import uuid4

from modules.agent.application.dtos.tools_dtos import ExecuteToolInput, ExecuteToolOutput
from modules.agent.application.dtos.mcp_tool_refresh_dtos import RefreshMcpProviderToolsInput
from modules.agent.application.interfaces.project_configuration import (
    configuration_for_session, current_tool_configuration,
)
from modules.agent.domain.enums import ToolStatus
from modules.agent.domain.errors import ToolNotFoundError
from modules.agent.domain.tool_configuration import tool_authentication, tool_dependencies
from modules.agent.infra.database.configuration_secret_projection import project_secret_headers
from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository
from shared.contracts.errors import AuthorizationError
from shared.contracts.project_configuration import ConfigurationError
from shared.presentation.contracts import OperationResult
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal
from shared.security.tenancy import TenantAuthorizer


class ConfiguredToolOperation:
    def __init__(self, uow_factory, legacy_handler, *, registry=None, preparation=None):
        self.uow_factory, self.legacy_handler = uow_factory, legacy_handler
        self.registry, self.preparation = registry, preparation

    async def __call__(self, request):
        refresh = self.preparation is not None
        dto = (RefreshMcpProviderToolsInput if refresh else ExecuteToolInput)(**request.body)
        permission = "tool:write" if refresh else "tool:execute"
        operation_id = uuid4()
        async with self.uow_factory() as uow:
            await self.authorize(uow.session, request.principal, dto.tool_id, permission)
            tool = await SQLAlchemyAgentToolRepository(uow.session).get_by_id(dto.tool_id)
            configuration = configuration_for_session(uow.session)
            if configuration is None:
                raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
            await configuration.lock_project(tool.project_id)
            # Reread after the cutover barrier, so a migration cannot change the
            # source between classification and acquisition.
            tool = await SQLAlchemyAgentToolRepository(uow.session).lock_by_id(dto.tool_id)
            tool = (await project_secret_headers(uow.session, project_id=tool.project_id, tools=[tool]))[0]
            auth = tool_authentication(tool.config, allow_legacy=True)
            if auth is not None and not refresh:
                if tool.status != ToolStatus.ACTIVE:
                    raise ToolNotFoundError(dto.tool_id)
                await configuration.acquire(project_id=tool.project_id, run_id=operation_id,
                    environment="draft", dependencies=tool_dependencies(tool))
        if auth is None:
            # An unconverted definition retains its existing contract. A failed
            # central operation never reaches this compatibility branch.
            return await self.legacy_handler()(request)
        if refresh:
            translated = request.model_copy(update={
                "path_params": {"project_id": tool.project_id, "target_id": tool.id},
                "body": {"environment": "draft"},
            })
            result = await self.preparation(translated, timeout_ms=dto.timeout_ms, legacy_refresh=True)
            data = result.body["data"]
            return OperationResult(body={"success": True, "message": "ok", "data": {
                "tool_id": str(tool.id), "discovered_count": data["discovered_count"],
                "initialized": data["initialized"], "status": data["state"],
                "error": None, "http_status": None, "phase": "configuration",
            }})
        token = current_tool_configuration.set((tool.project_id, operation_id, tool.id, auth))
        try:
            result = await self.registry.execute(tool, dto.input_data or {})
        finally:
            current_tool_configuration.reset(token)
        output = ExecuteToolOutput(success=result.success, output=result.output,
            duration_ms=result.duration_ms, error=result.error)
        return OperationResult(body={"success": True, "message": "ok", "data": output.model_dump()})

    @staticmethod
    async def authorize(session, principal, tool_id, permission):
        authorizer = TenantAuthorizer(session)
        context = {"tool_id": tool_id, "environment": "draft"}
        if isinstance(principal, ControlPlanePrincipal):
            await authorizer.require_active_control(principal)
            await authorizer.authorize_control_key(api_key_id=principal.api_key_id,
                workspace_id=principal.workspace_id, workspace_permissions=principal.permissions,
                required_permission=permission, path_params=context, query_params={}, body=None)
        elif isinstance(principal, AuthenticatedPrincipal):
            await authorizer.require_active_human(principal)
            await authorizer.authorize(user_id=principal.user_id, required_permission=permission,
                path_params=context, query_params={}, body=None, mutation=True)
        else:
            raise AuthorizationError("Administrative authentication is required")
