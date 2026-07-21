from __future__ import annotations

from uuid import UUID

from fastapi import Request

from shared.infra.errors import AuthorizationError
from shared.security.principal import AuthenticatedPrincipal


def require_evaluation_user(request: Request, project_id: UUID) -> UUID:
    """Require a control-plane user for Evaluation administration.

    Runtime and project API keys are intentionally rejected. Project tenancy is
    still enforced by the global HTTP guard before this dependency runs.
    """

    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, AuthenticatedPrincipal):
        raise AuthorizationError(
            "Evaluation administration requires an authenticated control-plane user"
        )
    return principal.user_id


__all__ = ["require_evaluation_user"]
