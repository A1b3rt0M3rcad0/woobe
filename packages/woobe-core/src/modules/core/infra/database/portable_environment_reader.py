"""Read environment key kinds only; values never cross the export boundary."""

from sqlalchemy import select
from modules.core.infra.database.models import ProjectEnvironmentKeyModel
from shared.security.tenancy import TenantAuthorizer
from shared.security.principal import ControlPlanePrincipal, AuthenticatedPrincipal
from shared.contracts.errors import AuthorizationError, ConflictError


class PortableEnvironmentReader:
    def __init__(self, sessions):
        self._sessions = sessions

    async def capture(self, *, project_id, principal, keys):
        if not keys:
            return {}
        async with self._sessions.begin() as session:
            authorizer = TenantAuthorizer(session)
            paths = {"project_id": str(project_id)}
            if isinstance(principal, ControlPlanePrincipal):
                await authorizer.require_active_control(principal)
                await authorizer.authorize_control_key(
                    api_key_id=principal.api_key_id,
                    workspace_id=principal.workspace_id,
                    workspace_permissions=principal.permissions,
                    required_permission="project:environment:read",
                    path_params=paths,
                    query_params={},
                    body={},
                )
            elif isinstance(principal, AuthenticatedPrincipal):
                await authorizer.require_active_human(principal)
                await authorizer.require_human_permission(
                    user_id=principal.user_id,
                    workspace_id=await authorizer._project_workspace_id(project_id),
                    project_id=project_id,
                    permission="project:environment:read",
                    path_context=paths,
                )
            else:
                raise AuthorizationError("Administrative authentication is required")
            result = await session.execute(
                select(
                    ProjectEnvironmentKeyModel.key, ProjectEnvironmentKeyModel.kind
                ).where(
                    ProjectEnvironmentKeyModel.project_id == project_id,
                    ProjectEnvironmentKeyModel.key.in_(keys),
                )
            )
            metadata = dict(result.all())
            if set(metadata) != set(keys):
                raise ConflictError("Export environment requirement is unavailable")
            return metadata
