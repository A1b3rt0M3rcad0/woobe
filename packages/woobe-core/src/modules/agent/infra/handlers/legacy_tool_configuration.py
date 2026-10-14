"""Bridge old Tool writes through explicit, transaction-current use authority."""
from uuid import UUID
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
        result = await self.handler(request)
        data = result.body.get('data') if isinstance(result.body,dict) else None
        if not isinstance(data,dict) or not data.get('id'):
            return result
        session = self.uow.session
        tool = await SQLAlchemyAgentToolRepository(session).get_by_id(UUID(str(data['id'])))
        projected = (await project_secret_headers(session,project_id=tool.project_id,tools=[tool]))[0]
        dependencies = [dep for dep in tool_dependencies(projected) if dep.legacy_alias_id is not None]
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
