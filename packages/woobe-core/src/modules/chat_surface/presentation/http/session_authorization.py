from uuid import UUID

from fastapi import Request

from modules.chat_surface.application.dtos.session_authorization import (
    AuthorizedChatSession,
)
from modules.chat_surface.composition.composers.session_authorization_composer import (
    authorize_chat_surface_session_composer,
)
from shared.contracts.errors import AuthenticationError, AuthorizationError
from shared.presentation.http.request import Request as InternalRequest


def _bearer(request: Request) -> str:
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not credentials:
        raise AuthenticationError("Bearer authentication required")
    return credentials


def _host_origin(value: str | None) -> str:
    if value is None or not value.strip():
        raise AuthorizationError("X-Woobe-Host-Origin is required")
    return value


async def authorize_session(
    request: Request,
    session_id: UUID,
    *,
    permission: str,
    host_origin: str | None,
) -> AuthorizedChatSession:
    response = await authorize_chat_surface_session_composer()(
        InternalRequest(
            body={
                "token": _bearer(request),
                "expected_session_id": str(session_id),
                "host_origin": _host_origin(host_origin),
                "permission": permission,
            }
        )
    )
    return AuthorizedChatSession.model_validate(response.body["data"])


__all__ = ["authorize_session"]
