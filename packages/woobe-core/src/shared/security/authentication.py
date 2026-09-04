from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


class SecurityAuthenticator(Protocol):
    """Transport-neutral contract for authenticating and authorizing principals."""

    async def authenticate_user(
        self,
        *,
        access_token: str,
        path_params: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: Any,
    ) -> AuthenticatedPrincipal: ...

    async def authenticate_api_key(
        self,
        *,
        credentials: str,
        required_scope: str | None,
        runtime_interface: str | None,
        path_params: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: Any,
    ) -> ProjectApiPrincipal: ...
