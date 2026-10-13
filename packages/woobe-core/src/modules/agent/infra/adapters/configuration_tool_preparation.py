"""Prepare a declared MCP connection without keeping SQL open over network I/O."""
from copy import deepcopy
from modules.agent.application.interfaces.tool_types import is_mcp_tool_type
from uuid import UUID, uuid4
from modules.agent.application.interfaces.project_configuration import configuration_for_session, current_tool_configuration
from modules.agent.domain.tool_configuration import tool_authentication, tool_dependencies
from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository
from shared.contracts.errors import AuthorizationError
from shared.contracts.project_configuration import ConfigurationError
from shared.runtime_environment import normalize_runtime_environment
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal
from shared.security.tenancy import TenantAuthorizer
from shared.presentation.contracts import OperationResult, OperationOutcome


class ConfigurationToolPreparation:
    def __init__(self, uow_factory, preparer):
        self.uow_factory, self.preparer = uow_factory, preparer

    async def __call__(self, request):
        project_id, target_id = UUID(str(request.path_params["project_id"])), UUID(str(request.path_params["target_id"]))
        environment = normalize_runtime_environment((request.body or {}).get("environment") or "draft")
        operation_id = uuid4()
        principal = request.principal
        async with self.uow_factory() as uow:
            await self._authorize(uow.session, principal, project_id, target_id, environment)
            tool = await SQLAlchemyAgentToolRepository(uow.session).get_by_id(target_id)
            if tool.project_id != project_id or not is_mcp_tool_type(tool.type):
                raise ConfigurationError("CONFIG_BINDING_INVALID")
            auth = tool_authentication(tool.config)
            if auth is None:
                raise ConfigurationError("LEGACY_FORMAT_UNSUPPORTED")
            configuration = configuration_for_session(uow.session)
            if configuration is None:
                raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
            await configuration.acquire(project_id=project_id, run_id=operation_id, environment=environment,
                dependencies=tool_dependencies(tool))
            original = deepcopy(tool.config)
            original_updated_at = tool.updated_at
        token = current_tool_configuration.set((project_id, operation_id, target_id, auth))
        try:
            result = await self.preparer.bootstrap(tool)
        finally:
            current_tool_configuration.reset(token)
        if result is None:
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        async with self.uow_factory() as uow:
            await self._authorize(uow.session, principal, project_id, target_id, environment)
            repository = SQLAlchemyAgentToolRepository(uow.session)
            current = await repository.lock_by_id(target_id)
            if current.config != original or current.updated_at != original_updated_at:
                raise ConfigurationError("CONFIG_REVISION_CONFLICT")
            current.config = tool.config
            await repository.update(current)
            if auth["fields"]:
                configuration = configuration_for_session(uow.session)
                await configuration.record_validation(project_id=project_id, run_id=operation_id,
                    consumer_kind="tool", consumer_id=target_id,
                    state="valid" if result.initialized and result.status == "ready" else "unknown", actor="configuration-validation")
        return OperationResult(outcome=OperationOutcome.SUCCESS, body={"success": True, "message": "ok", "data": {
            "target_kind": "tool", "target_id": str(target_id), "environment": environment,
            "state": result.status, "initialized": result.initialized, "discovered_count": result.discovered_count}})

    @staticmethod
    async def _authorize(session, principal, project_id, target_id, environment):
        authorizer = TenantAuthorizer(session)
        context = {"project_id": project_id, "tool_id": target_id, "environment": environment}
        for permission in ["tool:write", "project:environment:validate"]:
            if isinstance(principal, ControlPlanePrincipal):
                await authorizer.require_active_control(principal)
                await authorizer.authorize_control_key(api_key_id=principal.api_key_id, workspace_id=principal.workspace_id,
                    workspace_permissions=principal.permissions, required_permission=permission,
                    path_params=context, query_params={}, body=None)
            elif isinstance(principal, AuthenticatedPrincipal):
                await authorizer.require_active_human(principal)
                await authorizer.authorize(user_id=principal.user_id, required_permission=permission,
                    path_params=context, query_params={}, body=None)
            else:
                raise AuthorizationError("Administrative authentication is required")
