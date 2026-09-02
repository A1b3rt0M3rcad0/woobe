from uuid import UUID

from shared.contracts.errors import AuthorizationError
from shared.presentation.http.request import Request
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


def project_id_from_request(request: Request) -> UUID:
    value = request.path_params.get("project_id") or request.query_params.get("project_id")
    if value is None:
        raise AuthorizationError("Project context is required")
    return UUID(str(value))


def authorize_project(request: Request, project_id: UUID) -> None:
    principal = request.principal
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        return
    if isinstance(principal, AuthenticatedPrincipal):
        return
    raise AuthorizationError("Authentication required")
