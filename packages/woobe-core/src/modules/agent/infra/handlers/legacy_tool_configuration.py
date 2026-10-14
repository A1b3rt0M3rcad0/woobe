"""Bridge old Tool writes through explicit, transaction-current use authority."""
from uuid import UUID
from copy import deepcopy
from modules.agent.application.interfaces.project_configuration import configuration_for_session
from modules.agent.domain.tool_configuration import tool_dependencies
from modules.agent.infra.database.configuration_secret_projection import project_secret_headers
from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository
from shared.contracts.project_configuration import ConfigurationError
from shared.contracts.errors import AuthorizationError
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal
from shared.security.tenancy import TenantAuthorizer


class LegacyToolConfigurationHandler:
    def __init__(self, uow, handler):
        self.uow, self.handler = uow, handler

    async def __call__(self, request):
        incoming = (request.body or {}).get('config')
        identifier = request.path_params.get('tool_id')
        if identifier is not None and isinstance(incoming, dict):
            original = await SQLAlchemyAgentToolRepository(self.uow.session).lock_by_id(UUID(str(identifier)))
            proposed = deepcopy(original)
            proposed.config = incoming
            def public_bindings(tool):
                return {(dep.field_path, dep.key, dep.destination) for dep in tool_dependencies(tool)
                        if dep.legacy_alias_id is None}
            if public_bindings(original) != public_bindings(proposed):
                await self.require_binding_authority(self.uow.session, request.principal,
                    project_id=original.project_id, tool_id=original.id)
        result = await self.handler(request)
        data = result.body.get('data') if isinstance(result.body,dict) else None
        if not isinstance(data,dict) or not data.get('id'):
            return result
        session = self.uow.session
        tool = await SQLAlchemyAgentToolRepository(session).get_by_id(UUID(str(data['id'])))
        projected = (await project_secret_headers(session,project_id=tool.project_id,tools=[tool]))[0]
        owned = {dep.legacy_alias_id for dep in tool_dependencies(tool) if dep.legacy_alias_id is not None}
        dependencies = [dep for dep in tool_dependencies(projected)
            if dep.legacy_alias_id is not None and dep.legacy_alias_id not in owned]
        if not dependencies:
            return result
        store = configuration_for_session(session)
        if store is None:
            raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
        authorizer = TenantAuthorizer(session)
        principal = request.principal
        async def authorize(dependency,secret_id):
            for environment in ('draft','staging','production'):
                context={'project_id':tool.project_id,'tool_id':tool.id,'secret_id':secret_id,'environment':environment}
                for permission in ('secret:read','project:environment:use-policy:write'):
                    if isinstance(principal,ControlPlanePrincipal):
                        await authorizer.require_active_control(principal)
                        await authorizer.authorize_control_key(api_key_id=principal.api_key_id,
                            workspace_id=principal.workspace_id,workspace_permissions=principal.permissions,
                            required_permission=permission,path_params=context,query_params={},body=None)
                    elif isinstance(principal,AuthenticatedPrincipal):
                        await authorizer.require_active_human(principal)
                        await authorizer.authorize(user_id=principal.user_id,path_params=context,
                            query_params={},body=None,required_permission=permission,mutation=True)
                    else:
                        raise AuthorizationError('Legacy Secret use requires an authorized operator')
        actor = 'key:'+str(principal.api_key_id) if isinstance(principal,ControlPlanePrincipal) else 'user:'+str(getattr(principal,'user_id','unavailable'))
        await store.approve_legacy_consumers(project_id=tool.project_id,dependencies=dependencies,authorize=authorize,actor=actor)
        return result

    @staticmethod
    async def require_binding_authority(session, principal, *, project_id, tool_id):
        authorizer = TenantAuthorizer(session)
        context = {'project_id': project_id, 'tool_id': tool_id}
        if isinstance(principal, ControlPlanePrincipal):
            await authorizer.require_active_control(principal)
            await authorizer.authorize_control_key(api_key_id=principal.api_key_id,
                workspace_id=principal.workspace_id, workspace_permissions=principal.permissions,
                required_permission='project:environment:bind', path_params=context, query_params={}, body=None)
        elif isinstance(principal, AuthenticatedPrincipal):
            await authorizer.require_active_human(principal)
            await authorizer.authorize(user_id=principal.user_id, path_params=context,
                query_params={}, body=None, required_permission='project:environment:bind', mutation=True)
        else:
            raise AuthorizationError('Binding changes require an authorized operator')
