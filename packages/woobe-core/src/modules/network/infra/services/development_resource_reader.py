from uuid import UUID
from modules.network.infra.database.models import NetworkModel
from shared.contracts.errors import NotFoundError
from shared.security.tenancy import TenantAuthorizer
from shared.security.principal import ControlPlanePrincipal, AuthenticatedPrincipal


class DevelopmentNetworkReader:
    async def inspect(
        self, session, *, project_id, principal, kind, resource_id, lock=False, environment=None
    ):
        authorizer = TenantAuthorizer(session)
        paths = {"project_id": str(project_id), "network_id": str(resource_id)}
        if environment:
            paths["environment"] = environment
        if isinstance(principal, ControlPlanePrincipal):
            await authorizer.require_active_control(principal)
            await authorizer.authorize_control_key(
                api_key_id=principal.api_key_id,
                workspace_id=principal.workspace_id,
                workspace_permissions=principal.permissions,
                required_permission="network:read",
                path_params=paths,
                query_params={},
                body={},
            )
        elif isinstance(principal, AuthenticatedPrincipal):
            await authorizer.require_active_human(principal)
            workspace = await authorizer._project_workspace_id(project_id)
            await authorizer.require_human_permission(
                user_id=principal.user_id,
                workspace_id=workspace,
                project_id=project_id,
                permission="network:read",
                path_context=paths,
            )
        else:
            raise NotFoundError("Network is unavailable")
        row = await session.get(
            NetworkModel,
            UUID(str(resource_id)),
            with_for_update=lock,
            populate_existing=lock,
        )
        if row is None or row.project_id != project_id:
            raise NotFoundError("Network is unavailable")
        return {
            "resource_id": str(row.id),
            "kind": "Network",
            "revision": row.draft_revision,
        }
