from __future__ import annotations

from uuid import UUID, uuid4

from modules.agent.infra.database.models import SessionModel
from modules.chat_surface.infra.database.models import ChatSurfaceModel
from modules.chat_surface.presentation.schemas import CreateSurfaceSessionRequest
from modules.chat_surface.security import normalize_origin
from modules.chat_surface.service import (
    AuthorizedChatSession,
    ChatSurfaceService,
    SurfaceCredential,
)
from modules.core.infra.database.models import ApiKeyModel
from modules.network.infra.database.models import NetworkSessionModel
from shared.infra.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from shared.runtime_environment import assert_runtime_environment_enabled


CONTROL_PLANE_TEST_SOURCE = "control_plane_test"


class ControlPlaneChatSurfaceService(ChatSurfaceService):
    """Adds authenticated Control Plane testing without exposing Surface Access Keys."""

    async def create_test_session(
        self,
        *,
        surface_id: UUID,
        actor_id: UUID,
        origin: str,
    ):
        surface = await self.get_surface(surface_id)
        if surface.status != "active":
            raise ConflictError("ChatSurface must be active before it can be tested")

        normalized_origin = normalize_origin(
            origin,
            allow_insecure=self._allow_insecure_origins,
        )
        synthetic_credential = SurfaceCredential(
            api_key_id=uuid4(),
            project_id=surface.project_id,
            chat_surface_id=surface.id,
            scopes=frozenset({"surface:sessions:create"}),
        )
        binding = await self.create_session(
            surface=surface,
            credential=synthetic_credential,
            idempotency_key=f"control-plane-test:{uuid4()}",
            payload=CreateSurfaceSessionRequest(
                metadata={
                    "source": CONTROL_PLANE_TEST_SOURCE,
                    "actor_id": str(actor_id),
                }
            ),
        )

        refreshed_surface = await self.get_surface(surface.id)
        if refreshed_surface.status != "active":
            raise ConflictError("ChatSurface became inactive while creating the test Session")

        token = self._token_codec.issue(
            project_id=refreshed_surface.project_id,
            chat_surface_id=refreshed_surface.id,
            target_type=refreshed_surface.target_type,
            target_id=refreshed_surface.target_id,
            target_release_id=binding.target_release_id,
            session_id=binding.session_id,
            origin=normalized_origin,
            surface_credential_id=binding.surface_credential_id,
            token_epoch=refreshed_surface.token_epoch,
            ttl_seconds=refreshed_surface.session_token_ttl_seconds,
        )
        return token, binding, refreshed_surface

    async def authorize_session_token(
        self,
        token: str,
        *,
        expected_session_id: UUID,
        host_origin: str | None,
        permission: str,
    ) -> AuthorizedChatSession:
        claims = self._token_codec.decode(token)
        if claims.session_id != expected_session_id:
            raise NotFoundError("ChatSurface Session not found")
        if permission not in claims.permissions:
            raise AuthorizationError("ChatSurface Session token scope is insufficient")

        binding = await self.get_binding(
            surface_id=claims.chat_surface_id,
            session_id=claims.session_id,
        )
        metadata = dict(binding.metadata_ or {})
        if metadata.get("source") != CONTROL_PLANE_TEST_SOURCE:
            return await super().authorize_session_token(
                token,
                expected_session_id=expected_session_id,
                host_origin=host_origin,
                permission=permission,
            )

        if not host_origin:
            raise AuthorizationError("X-Woobe-Host-Origin is required")
        normalized_origin = normalize_origin(
            host_origin,
            allow_insecure=self._allow_insecure_origins,
        )
        if normalized_origin != claims.origin:
            raise AuthorizationError("ChatSurface Session origin does not match")
        if binding.surface_credential_id != claims.surface_credential_id:
            raise AuthenticationError("ChatSurface test Session token is inactive")

        async with self._session_factory() as session:
            # Public Sessions always point to a persisted Access Key. A Control Plane
            # test Session deliberately uses a synthetic UUID, so externally supplied
            # metadata cannot opt into the relaxed origin policy.
            credential = await session.get(ApiKeyModel, claims.surface_credential_id)
            if credential is not None:
                raise AuthenticationError("ChatSurface test Session token is inactive")

            surface = await session.get(ChatSurfaceModel, claims.chat_surface_id)
            if (
                surface is None
                or surface.status != "active"
                or surface.project_id != claims.project_id
                or surface.target_type != claims.target_type
                or surface.target_id != claims.target_id
                or surface.token_epoch != claims.token_epoch
                or binding.status != "active"
                or binding.project_id != claims.project_id
                or binding.target_type != claims.target_type
                or binding.target_id != claims.target_id
                or binding.target_release_id != claims.target_release_id
            ):
                raise AuthenticationError("ChatSurface test Session token is inactive")

            await assert_runtime_environment_enabled(
                session,
                target_type=surface.target_type,
                target_id=surface.target_id,
                project_id=surface.project_id,
                environment="production",
            )

            if binding.target_type == "agent":
                target_session = await session.get(SessionModel, binding.session_id)
                valid_target_session = (
                    target_session is not None
                    and target_session.project_id == binding.project_id
                    and target_session.agent_id == binding.target_id
                    and target_session.runtime_environment == "production"
                    and target_session.opened_release_id == binding.target_release_id
                    and target_session.chat_surface_id == surface.id
                    and target_session.origin == "chat_surface"
                    and target_session.status == "active"
                )
            else:
                target_session = await session.get(
                    NetworkSessionModel,
                    binding.session_id,
                )
                valid_target_session = (
                    target_session is not None
                    and target_session.project_id == binding.project_id
                    and target_session.network_id == binding.target_id
                    and target_session.environment == "production"
                    and target_session.network_version_id == binding.target_release_id
                    and target_session.chat_surface_id == surface.id
                    and target_session.origin == "chat_surface"
                    and target_session.status == "active"
                )
            if not valid_target_session:
                raise NotFoundError("ChatSurface Session not found")

            return AuthorizedChatSession(
                surface=surface,
                binding=binding,
                claims=claims,
            )


__all__ = ["CONTROL_PLANE_TEST_SOURCE", "ControlPlaneChatSurfaceService"]
